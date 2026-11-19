"""O servidor HTTP do assistente: quem pode usar, limites e o formato da resposta transmitida."""

import json
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

import agente
import config
import main
from sessoes import LimiteDeUso, Sessoes

ORIGEM_OK = "http://127.0.0.1:5500"


@pytest.fixture
def cliente(monkeypatch: pytest.MonkeyPatch):
    # Estado limpo a cada teste, chave "configurada" e um agente de mentira.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    monkeypatch.setattr(main, "sessoes", Sessoes())
    monkeypatch.setattr(main, "limite_de_uso", LimiteDeUso())
    chamadas: list[tuple[str, str]] = []
    chamadas_perfil: list[str] = []

    async def conversar_falso(sessao, pergunta):
        chamadas.append((sessao.id, pergunta))
        chamadas_perfil.append(sessao.perfil)
        yield {"type": "texto", "texto": "Olá"}
        sessao.turnos += 1
        yield {"type": "fim", "uso": {}}

    monkeypatch.setattr(agente, "conversar", conversar_falso)
    http = TestClient(main.criar_app(), base_url="http://127.0.0.1:8100")
    http.chamadas = chamadas  # type: ignore[attr-defined]
    http.perfis = chamadas_perfil  # type: ignore[attr-defined]
    return http


def eventos(resposta) -> list[dict]:
    linhas = [l for l in resposta.text.split("\n\n") if l.startswith("data: ")]
    return [json.loads(l[len("data: "):]) for l in linhas]


def perguntar(cliente, mensagem="oi", sessao_id=None, origem=ORIGEM_OK, perfil=None):
    corpo = {"mensagem": mensagem}
    if perfil:
        corpo["perfil"] = perfil
    if sessao_id:
        corpo["sessaoId"] = sessao_id
    return cliente.post("/chat", json=corpo, headers={"Origin": origem} if origem else {})


def test_resposta_transmitida_em_eventos(cliente):
    resposta = perguntar(cliente)

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/event-stream")
    lista = eventos(resposta)
    assert [e["type"] for e in lista] == ["inicio", "texto", "fim"]
    assert lista[0]["sessaoId"]
    assert resposta.headers["access-control-allow-origin"] == ORIGEM_OK


def test_mesma_conversa_reaproveita_a_sessao(cliente):
    sessao_id = eventos(perguntar(cliente, "primeira"))[0]["sessaoId"]
    segunda = eventos(perguntar(cliente, "segunda", sessao_id))[0]["sessaoId"]

    assert segunda == sessao_id
    assert [c[1] for c in cliente.chamadas] == ["primeira", "segunda"]
    assert len({c[0] for c in cliente.chamadas}) == 1


def test_sessao_desconhecida_vira_conversa_nova(cliente):
    novo = eventos(perguntar(cliente, "oi", "id-inventado"))[0]["sessaoId"]
    assert novo != "id-inventado"


def test_origem_nao_autorizada_e_recusada_sem_gastar_tokens(cliente):
    resposta = perguntar(cliente, origem="http://site-de-terceiros.com")
    assert resposta.status_code == 403
    assert cliente.chamadas == []


def test_chamada_sem_origem_e_aceita(cliente):
    # curl e testes locais não enviam Origin; navegadores sempre enviam.
    assert perguntar(cliente, origem=None).status_code == 200


def test_sem_chave_da_api_explica_o_que_fazer(cliente, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    resposta = perguntar(cliente)
    assert resposta.status_code == 503
    assert "ANTHROPIC_API_KEY" in resposta.json()["erro"]


@pytest.mark.parametrize("corpo", [{}, {"mensagem": ""}, {"mensagem": "   "}, {"mensagem": 42}, [], "texto"])
def test_pergunta_invalida(cliente, corpo):
    resposta = cliente.post("/chat", json=corpo, headers={"Origin": ORIGEM_OK})
    assert resposta.status_code == 400


def test_corpo_que_nao_e_json(cliente):
    resposta = cliente.post("/chat", content="não é json", headers={"Origin": ORIGEM_OK})
    assert resposta.status_code == 400


def test_pergunta_longa_demais(cliente):
    resposta = perguntar(cliente, "x" * (config.LIMITE_PERGUNTA + 1))
    assert resposta.status_code == 413


def test_limite_de_perguntas_por_minuto(cliente, monkeypatch):
    monkeypatch.setattr(config, "LIMITE_POR_MINUTO", 2)
    assert perguntar(cliente).status_code == 200
    assert perguntar(cliente).status_code == 200
    assert perguntar(cliente).status_code == 429


def test_conversa_longa_pede_uma_nova(cliente, monkeypatch):
    monkeypatch.setattr(config, "LIMITE_TURNOS", 1)
    sessao_id = eventos(perguntar(cliente))[0]["sessaoId"]
    resposta = perguntar(cliente, "mais uma", sessao_id)
    assert resposta.status_code == 409
    assert "nova conversa" in resposta.json()["erro"]


def test_cors_preflight_so_para_o_frontend_autorizado(cliente):
    cabecalhos = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    certo = cliente.options("/chat", headers={"Origin": ORIGEM_OK, **cabecalhos})
    assert certo.status_code == 200 and certo.headers["access-control-allow-origin"] == ORIGEM_OK
    errado = cliente.options("/chat", headers={"Origin": "http://outro.com", **cabecalhos})
    assert "access-control-allow-origin" not in errado.headers


def test_estado_informa_chave_e_mcp_sem_expor_a_chave(cliente, monkeypatch):
    class MCPFalso:
        def __init__(self, url):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def list_tools(self):
            return SimpleNamespace(tools=[1, 2, 3])

    monkeypatch.setattr(main, "Client", MCPFalso)
    dados = cliente.get("/").json()

    assert dados["chaveConfigurada"] is True
    assert dados["modelo"] == "claude-sonnet-5-5"
    assert dados["mcp"] == {"url": config.MCP_URL, "acessivel": True, "tools": 3}
    assert "chave-de-teste" not in json.dumps(dados)


def test_estado_com_mcp_fora_do_ar(cliente, monkeypatch):
    class MCPQuebrado:
        def __init__(self, url):
            pass

        async def __aenter__(self):
            raise ConnectionError("recusada")

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(main, "Client", MCPQuebrado)
    assert cliente.get("/").json()["mcp"]["acessivel"] is False


def test_perfil_padrao_e_o_mais_restrito_cidadao(cliente):
    perguntar(cliente)
    assert cliente.perfis == ["cidadao"]


def test_perfil_defesa_civil_e_aceito(cliente):
    perguntar(cliente, perfil="defesa_civil")
    assert cliente.perfis == ["defesa_civil"]


@pytest.mark.parametrize("perfil", ["admin", "", 7, None])
def test_perfil_invalido(cliente, perfil):
    resposta = cliente.post("/chat", json={"mensagem": "oi", "perfil": perfil}, headers={"Origin": ORIGEM_OK})
    assert resposta.status_code == 400


def test_trocar_de_perfil_comeca_conversa_nova(cliente):
    id_cidadao = eventos(perguntar(cliente, "oi", perfil="cidadao"))[0]["sessaoId"]
    id_operador = eventos(perguntar(cliente, "oi", id_cidadao, perfil="defesa_civil"))[0]["sessaoId"]
    assert id_operador != id_cidadao
