"""O assistente com o SDK REAL da Anthropic, contra um servidor HTTP de mentira.

O servidor de mentira responde no formato de streaming (SSE) da API do Claude. Assim o SDK
monta e envia as requisições de verdade, e conferimos o que sairia pela rede: modelo,
tools, esforço, cabeçalho beta, histórico. Nenhum token é gasto e nenhuma chave é necessária.
"""

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

import agente
import config
from sessoes import Sessao
from tests.conftest import MCPFalso, coletar


def sse(*eventos: tuple[str, dict[str, Any]]) -> bytes:
    return "".join(f"event: {nome}\ndata: {json.dumps(dados)}\n\n" for nome, dados in eventos).encode()


def mensagem_de_texto(texto: str, stop: str = "end_turn") -> bytes:
    return sse(
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5", "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 120, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": texto}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 9}}),
        ("message_stop", {"type": "message_stop"}),
    )  # fmt: skip


def mensagem_com_tool(id_: str, nome: str, entrada: dict[str, Any]) -> bytes:
    return sse(
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_0", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5", "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 300, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Vou consultar. "}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("content_block_start", {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": id_, "name": nome, "input": {}}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": json.dumps(entrada)}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 1}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None}, "usage": {"output_tokens": 30}}),
        ("message_stop", {"type": "message_stop"}),
    )  # fmt: skip


class ApiFalsa:
    """Responde, em ordem, as mensagens do roteiro e guarda o que o SDK enviou."""

    def __init__(self, roteiro: list[Any]) -> None:
        self.roteiro = list(roteiro)
        self.requisicoes: list[SimpleNamespace] = []

    def __call__(self, requisicao: httpx2.Request) -> httpx2.Response:
        self.requisicoes.append(
            SimpleNamespace(url=str(requisicao.url), cabecalhos=dict(requisicao.headers), corpo=json.loads(requisicao.content))
        )
        proximo = self.roteiro.pop(0)
        if isinstance(proximo, httpx2.Response):
            return proximo
        return httpx2.Response(200, content=proximo, headers={"content-type": "text/event-stream"})


@pytest.fixture
def api():
    def instalar(roteiro: list[Any]) -> ApiFalsa:
        falsa = ApiFalsa(roteiro)
        cliente = anthropic.AsyncAnthropic(
            api_key="chave-de-teste",
            max_retries=0,
            http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(falsa)),
        )
        agente.usar_cliente_ia(cliente)
        return falsa

    yield instalar
    agente.usar_cliente_ia(None)


async def test_pergunta_com_tool_de_ponta_a_ponta(api, monkeypatch):
    mcp = MCPFalso({"analisar_risco": {"situacao": "ALERTA", "areasMaisAfetadas": ["Norte"]}})
    monkeypatch.setattr(agente, "Client", mcp)
    monkeypatch.setattr(config, "USAR_FALLBACK", False)
    rede = api([mensagem_com_tool("toolu_1", "analisar_risco", {"regiao": "Norte"}), mensagem_de_texto("O Norte está em alerta.")])
    sessao = Sessao(id="s", perfil="defesa_civil")

    eventos = await coletar(agente.conversar(sessao, "Risco no Norte?"))

    # O texto chegou em pedaços e a tool do MCP foi chamada com a entrada que o Claude montou.
    assert "".join(e["texto"] for e in eventos if e["type"] == "texto") == "Vou consultar. O Norte está em alerta."
    assert mcp.chamadas == [("analisar_risco", {"regiao": "Norte"})]
    assert eventos[-1]["type"] == "fim" and eventos[-1]["uso"] == {
        "entrada": 420, "saida": 39, "cache_lido": 0, "rodadas": 2, "tools": 1,
    }  # fmt: skip

    # 1ª requisição: o que o SDK realmente enviaria pela rede.
    primeira = rede.requisicoes[0]
    assert primeira.url.endswith("/v1/messages") and "beta" not in primeira.url
    assert primeira.cabecalhos["x-api-key"] == "chave-de-teste"
    corpo = primeira.corpo
    assert corpo["model"] == "claude-sonnet-5-5" and corpo["stream"] is True
    assert corpo["output_config"] == {"effort": "medium"} and corpo["cache_control"] == {"type": "ephemeral"}
    assert [t["name"] for t in corpo["tools"]] == ["analisar_risco", "consultar_canais"]
    assert "thinking" not in corpo and "tool_choice" not in corpo
    assert corpo["messages"] == [{"role": "user", "content": "Risco no Norte?"}]

    # 2ª requisição: o histórico cresce (pergunta -> pedido de tool -> resultado) sem editar nada.
    historico = rede.requisicoes[1].corpo["messages"]
    assert [m["role"] for m in historico] == ["user", "assistant", "user"]
    assert historico[1]["content"][1]["type"] == "tool_use" and historico[1]["content"][1]["id"] == "toolu_1"
    resultado = historico[2]["content"][0]
    assert resultado["type"] == "tool_result" and resultado["tool_use_id"] == "toolu_1"
    assert json.loads(resultado["content"])["situacao"] == "ALERTA"


async def test_fallback_usa_o_endpoint_beta_com_o_cabecalho_certo(api, monkeypatch):
    monkeypatch.setattr(agente, "Client", MCPFalso())
    monkeypatch.setattr(config, "USAR_FALLBACK", True)
    rede = api([mensagem_de_texto("ok")])

    eventos = await coletar(agente.conversar(Sessao(id="s"), "oi"))

    assert eventos[-1]["type"] == "fim"
    pedido = rede.requisicoes[0]
    assert "beta=true" in pedido.url
    assert "server-side-fallback-2026-07-01" in pedido.cabecalhos["anthropic-beta"]
    assert pedido.corpo["fallbacks"] == "default"


async def test_conta_sem_acesso_ao_fallback_cai_para_o_endpoint_normal(api, monkeypatch):
    monkeypatch.setattr(agente, "Client", MCPFalso())
    monkeypatch.setattr(config, "USAR_FALLBACK", True)
    erro = httpx2.Response(400, json={"type": "error", "error": {"type": "invalid_request_error", "message": "fallbacks is not available for this organization"}})
    rede = api([erro, mensagem_de_texto("ok")])

    eventos = await coletar(agente.conversar(Sessao(id="s"), "oi"))

    assert eventos[-1]["type"] == "fim"
    assert ["beta=true" in r.url for r in rede.requisicoes] == [True, False]


async def test_chave_recusada_pela_api_vira_mensagem_clara(api, monkeypatch):
    monkeypatch.setattr(agente, "Client", MCPFalso())
    monkeypatch.setattr(config, "USAR_FALLBACK", False)
    api([httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})])

    eventos = await coletar(agente.conversar(Sessao(id="s"), "oi"))

    assert eventos == [{"type": "erro", "mensagem": "A chave da API da Anthropic é inválida. Confira o ANTHROPIC_API_KEY no arquivo .env do assistente."}]
