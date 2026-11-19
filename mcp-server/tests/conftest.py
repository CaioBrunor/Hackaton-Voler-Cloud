import httpx
import pytest

from client.backend_client import BackendClient, usar_backend
from tests import dados_simulados


class BackendSimulado:
    """Faz o papel do Spring Boot: responde às rotas de dados_simulados.ROTAS."""

    def __init__(self) -> None:
        self.rotas = dict(dados_simulados.ROTAS)
        self.fora_do_ar: set[str] = set()
        self.chamadas: list[tuple[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.chamadas.append((request.method, str(request.url)))
        caminho = request.url.path
        if request.method != "GET":
            return httpx.Response(405)
        if caminho in self.fora_do_ar:
            return httpx.Response(503)
        if caminho not in self.rotas:
            return httpx.Response(404, json={"mensagem": "Não encontrado"})
        return httpx.Response(200, json=self.rotas[caminho])


def _usar_transporte(handler) -> None:
    usar_backend(BackendClient("http://backend.teste", timeout=5, transport=httpx.MockTransport(handler)))


@pytest.fixture
def backend():
    simulado = BackendSimulado()
    _usar_transporte(simulado)
    yield simulado
    usar_backend(None)


@pytest.fixture
def backend_desligado():
    def recusar_conexao(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexão recusada", request=request)

    _usar_transporte(recusar_conexao)
    yield
    usar_backend(None)


@pytest.fixture
def backend_lento():
    def estourar_tempo(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("tempo esgotado", request=request)

    _usar_transporte(estourar_tempo)
    yield
    usar_backend(None)
