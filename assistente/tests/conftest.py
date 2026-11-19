"""Dublês do Claude e do MCP Server para testar a lógica do assistente sem rede e sem gastar tokens."""

from types import SimpleNamespace
from typing import Any

import httpx2
import pytest

import agente
import config
from sessoes import Sessao

TOOLS_DO_MCP = [
    SimpleNamespace(
        name="analisar_risco",
        description="Analisa o risco de alagamento.",
        input_schema={"type": "object", "properties": {"regiao": {"type": "string"}}},
    ),
    SimpleNamespace(
        name="consultar_canais",
        description="Lista os canais.",
        input_schema={"type": "object", "properties": {}},
    ),
]


# ---------------------------------------------------------------- blocos e mensagens do Claude


def texto(conteudo: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=conteudo)


def pedido_de_tool(id_: str, nome: str, entrada: dict[str, Any] | None = None) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id_, name=nome, input=entrada or {})


def mensagem(blocos: list[Any], stop_reason: str = "end_turn", entrada: int = 100, saida: int = 20) -> SimpleNamespace:
    uso = SimpleNamespace(input_tokens=entrada, output_tokens=saida, cache_read_input_tokens=0)
    return SimpleNamespace(content=blocos, stop_reason=stop_reason, usage=uso)


class FluxoFalso:
    """O que o SDK devolve em `async with client.messages.stream(...)`."""

    def __init__(self, resposta: SimpleNamespace, pensar: bool = False) -> None:
        self._resposta = resposta
        self._pensar = pensar

    async def __aenter__(self) -> "FluxoFalso":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    def __aiter__(self):
        return self._eventos()

    async def _eventos(self):
        if self._pensar:
            yield SimpleNamespace(type="content_block_start", content_block=SimpleNamespace(type="thinking"))
        for bloco in self._resposta.content:
            if bloco.type == "text":
                yield SimpleNamespace(type="text", text=bloco.text)

    async def get_final_message(self) -> SimpleNamespace:
        return self._resposta


class ClaudeFalso:
    """Responde, em ordem, o roteiro combinado. Guarda os parâmetros de cada chamada."""

    def __init__(self, roteiro: list[Any]) -> None:
        self.roteiro = list(roteiro)
        self.chamadas: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(stream=self._abrir)
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._abrir_beta))

    def _abrir(self, **parametros: Any) -> FluxoFalso:
        self.chamadas.append({**parametros, "messages": list(parametros["messages"]), "_via": "messages"})
        proximo = self.roteiro.pop(0)
        if isinstance(proximo, Exception):
            raise proximo
        return FluxoFalso(proximo, pensar=True)

    def _abrir_beta(self, **parametros: Any) -> FluxoFalso:
        self.chamadas.append({**parametros, "messages": list(parametros["messages"]), "_via": "beta"})
        proximo = self.roteiro.pop(0)
        if isinstance(proximo, Exception):
            raise proximo
        return FluxoFalso(proximo, pensar=True)


# ---------------------------------------------------------------- MCP falso


class MCPFalso:
    """Cliente MCP de mentira: guarda as chamadas e devolve os resultados combinados."""

    def __init__(self, resultados: dict[str, Any] | None = None) -> None:
        self.resultados = resultados or {}
        self.chamadas: list[tuple[str, dict[str, Any]]] = []
        self.falha_ao_conectar: Exception | None = None

    def __call__(self, url: str) -> "MCPFalso":  # imita Client(url)
        self.url = url
        return self

    async def __aenter__(self) -> "MCPFalso":
        if self.falha_ao_conectar:
            raise self.falha_ao_conectar
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def list_tools(self) -> SimpleNamespace:
        return SimpleNamespace(tools=TOOLS_DO_MCP)

    async def call_tool(self, nome: str, argumentos: dict[str, Any]) -> SimpleNamespace:
        self.chamadas.append((nome, argumentos))
        dados = self.resultados.get(nome, {"total": 0})
        return SimpleNamespace(structured_content=dados, content=[], is_error=False)


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def mcp(monkeypatch: pytest.MonkeyPatch) -> MCPFalso:
    falso = MCPFalso()
    monkeypatch.setattr(agente, "Client", falso)
    return falso


@pytest.fixture
def claude():
    """Fábrica: claude(roteiro) instala um Claude de mentira e o devolve."""

    def instalar(roteiro: list[Any]) -> ClaudeFalso:
        falso = ClaudeFalso(roteiro)
        agente.usar_cliente_ia(falso)
        return falso

    yield instalar
    agente.usar_cliente_ia(None)


@pytest.fixture
def sessao() -> Sessao:
    return Sessao(id="s1")


@pytest.fixture(autouse=True)
def sem_fallback_por_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "USAR_FALLBACK", False)


async def coletar(gerador) -> list[dict[str, Any]]:
    return [evento async for evento in gerador]


def erro_400(mensagem_do_erro: str):
    import anthropic

    requisicao = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    resposta = httpx2.Response(400, request=requisicao, json={"error": {"message": mensagem_do_erro}})
    return anthropic.BadRequestError(mensagem_do_erro, response=resposta, body=None)
