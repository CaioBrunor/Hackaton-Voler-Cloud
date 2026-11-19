"""Cliente HTTP do backend Spring Boot: o único ponto do MCP que acessa a API.

Regras deste módulo:
* só faz requisições GET, porque o MCP é somente de consulta (não existe método
  para POST, PUT ou DELETE);
* a URL base e o tempo limite vêm do config.py;
* qualquer falha vira uma exceção com mensagem compreensível, que as tools
  devolvem à IA no formato {"erro": ..., "detalhe": ...}.
"""

import functools
import logging
import ssl
import time
from typing import Any

import httpx

import config
from models.schemas import ErroConsulta

logger = logging.getLogger("anti_enchente.backend")

# Rotas GET do backend Spring Boot (pasta backend/ do projeto). Se uma rota mudar, ajuste só aqui.
ENDPOINTS = {
    "previsao_chuva": "/api/previsoes-chuva",
    "sensores": "/api/sensores",
    "canais": "/api/canais",
    "bueiros": "/api/bueiros",
    "barragens": "/api/barragens",
    "areas_risco": "/api/areas-risco",
    "alertas": "/api/alertas",
    "ocorrencias": "/api/ocorrencias",
}

# Rotas opcionais: o backend atual ainda não as tem. Enquanto não existirem (404), o MCP
# calcula o resumo a partir das listas e informa que o histórico não está disponível.
ENDPOINTS_OPCIONAIS = {
    "resumo": "/api/dashboard/resumo",
    "historico_sensor": "/api/sensores/{id}/historico",
}

BACKEND_FORA_DO_AR = "Não foi possível consultar o backend."


@functools.cache
def _contexto_ssl() -> ssl.SSLContext:
    # Carregar os certificados custa ~200 ms. Criado uma vez e reaproveitado, evita
    # que cada requisição pague esse custo (analisar_risco faz 7 em paralelo).
    return httpx.create_ssl_context()


class BackendIndisponivel(ErroConsulta):
    """O backend não respondeu, demorou demais ou retornou erro interno (5xx)."""


class RecursoNaoEncontrado(ErroConsulta):
    """O backend respondeu 404 para o registro pedido."""


def _como_lista(dados: Any) -> list[Any]:
    """Aceita lista pura, página do Spring Data ({"content": [...]}) ou um único objeto."""
    if dados is None:
        return []
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for chave in ("content", "dados", "items"):
            if isinstance(dados.get(chave), list):
                return dados[chave]
        return [dados]
    raise ErroConsulta("O backend retornou dados em formato inesperado.", "Era esperada uma lista de registros.")


def _procurar_por_id(itens: list[Any], id: int, entidade: str) -> dict[str, Any]:
    for item in itens:
        if isinstance(item, dict) and str(item.get("id")) == str(id):
            return item
    raise RecursoNaoEncontrado("Registro não encontrado no backend.", f"{entidade} com id {id} não existe.")


def _como_objeto(dados: Any) -> dict[str, Any]:
    if not isinstance(dados, dict):
        raise ErroConsulta("O backend retornou dados em formato inesperado.", "Era esperado um objeto JSON.")
    return dados


class BackendClient:
    def __init__(self, base_url: str, timeout: float, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Nos testes, o transporte é trocado por um backend simulado (httpx.MockTransport).
        self._transport = transport

    async def _get(self, caminho: str, params: dict[str, str] | None = None) -> Any:
        inicio = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                verify=_contexto_ssl(),
                transport=self._transport,
                headers={"Accept": "application/json"},
            ) as http:
                resposta = await http.get(caminho, params=params)
        except httpx.TimeoutException:
            raise BackendIndisponivel(
                BACKEND_FORA_DO_AR, f"O backend não respondeu em {self.timeout:g} segundos."
            ) from None
        except httpx.HTTPError:
            raise BackendIndisponivel(BACKEND_FORA_DO_AR, "Serviço temporariamente indisponível.") from None

        tempo_ms = (time.perf_counter() - inicio) * 1000
        logger.debug("GET %s -> %s (%.0f ms)", caminho, resposta.status_code, tempo_ms)

        if resposta.status_code == 404:
            raise RecursoNaoEncontrado("Registro não encontrado no backend.", f"GET {caminho} retornou 404.")
        if resposta.status_code >= 500:
            raise BackendIndisponivel(BACKEND_FORA_DO_AR, f"O backend retornou erro {resposta.status_code}.")
        if not resposta.is_success:
            raise ErroConsulta("O backend recusou a consulta.", f"GET {caminho} retornou {resposta.status_code}.")
        if not resposta.content:
            return None
        try:
            return resposta.json()
        except ValueError:
            raise ErroConsulta("O backend retornou dados em formato inesperado.", "A resposta não é um JSON válido.") from None

    # ---------------------------------------------------------------- situação geral

    async def resumo_cidade(self) -> dict[str, Any]:
        """Resumo pronto do backend (rota opcional: 404 se o backend não a tiver)."""
        return _como_objeto(await self._get(ENDPOINTS_OPCIONAIS["resumo"]))

    async def previsao_chuva(self) -> list[Any]:
        return _como_lista(await self._get(ENDPOINTS["previsao_chuva"]))

    # ---------------------------------------------------------------- sensores

    async def listar_sensores(self) -> list[Any]:
        return _como_lista(await self._get(ENDPOINTS["sensores"]))

    async def obter_sensor(self, id: int) -> dict[str, Any]:
        # O backend não tem GET por id: o registro é procurado na lista.
        return _procurar_por_id(await self.listar_sensores(), id, "Sensor")

    async def historico_sensor(self, id: int, periodo: str) -> list[Any]:
        # int(id) garante que o valor não altere o caminho da URL.
        caminho = ENDPOINTS_OPCIONAIS["historico_sensor"].format(id=int(id))
        return _como_lista(await self._get(caminho, params={"periodo": periodo}))

    # ---------------------------------------------------------------- drenagem

    async def listar_canais(self) -> list[Any]:
        return _como_lista(await self._get(ENDPOINTS["canais"]))

    async def obter_canal(self, id: int) -> dict[str, Any]:
        return _procurar_por_id(await self.listar_canais(), id, "Canal")

    async def listar_bueiros(self) -> list[Any]:
        return _como_lista(await self._get(ENDPOINTS["bueiros"]))

    async def listar_barragens(self) -> list[Any]:
        return _como_lista(await self._get(ENDPOINTS["barragens"]))

    # ---------------------------------------------------------------- defesa civil

    async def listar_areas_risco(self) -> list[Any]:
        return _como_lista(await self._get(ENDPOINTS["areas_risco"]))

    async def listar_alertas(self) -> list[Any]:
        """Todos os alertas; quem filtra os ativos é a tool (o backend não tem rota própria)."""
        return _como_lista(await self._get(ENDPOINTS["alertas"]))

    async def listar_ocorrencias(self) -> list[Any]:
        """Todas as ocorrências; quem filtra as abertas é a tool."""
        return _como_lista(await self._get(ENDPOINTS["ocorrencias"]))


_cliente: BackendClient | None = None


def obter_backend() -> BackendClient:
    """Cliente compartilhado por todas as tools, criado a partir do config.py."""
    global _cliente
    if _cliente is None:
        _cliente = BackendClient(config.BACKEND_URL, config.API_TIMEOUT)
    return _cliente


def usar_backend(cliente: BackendClient | None) -> None:
    """Troca o cliente compartilhado (usado nos testes com um backend simulado)."""
    global _cliente
    _cliente = cliente
