"""O laço Claude <-> MCP: quem pede o quê, em que ordem, e o que acontece quando algo falha."""

import anthropic
import httpx2

import agente
import config
from tests.conftest import coletar, erro_400, mensagem, pedido_de_tool, texto


async def test_resposta_simples_sem_tools(claude, mcp, sessao):
    ia = claude([mensagem([texto("Tudo normal por aqui.")])])

    eventos = await coletar(agente.conversar(sessao, "Como está a cidade?"))

    tipos = [e["type"] for e in eventos]
    assert tipos == ["pensando", "texto", "fim"]
    assert eventos[1]["texto"] == "Tudo normal por aqui."
    assert eventos[-1]["uso"]["rodadas"] == 1
    # A conversa guardada só cresce quando a pergunta termina bem: pergunta + resposta.
    assert [m["role"] for m in sessao.mensagens] == ["user", "assistant"]
    assert sessao.turnos == 1
    assert len(ia.chamadas) == 1


async def test_parametros_enviados_ao_claude(claude, mcp, sessao):
    ia = claude([mensagem([texto("ok")])])

    await coletar(agente.conversar(sessao, "oi"))

    chamada = ia.chamadas[0]
    assert chamada["model"] == "claude-sonnet-5-5"
    assert chamada["output_config"] == {"effort": "medium"}
    assert chamada["cache_control"] == {"type": "ephemeral"}
    assert chamada["max_tokens"] == config.MAX_TOKENS
    assert "Defesa Civil" in chamada["system"]
    # O Sonnet 5.5 não aceita tool_choice forçado nem pensar desligado: o assistente não envia nenhum dos dois.
    assert "tool_choice" not in chamada
    assert "thinking" not in chamada
    # As tools do MCP viram tools do Claude, com nome, descrição e esquema.
    assert [t["name"] for t in chamada["tools"]] == ["analisar_risco", "consultar_canais"]
    assert chamada["tools"][0]["input_schema"]["properties"] == {"regiao": {"type": "string"}}
    assert chamada["messages"][0] == {"role": "user", "content": "oi"}


async def test_claude_usa_tools_do_mcp_em_paralelo(claude, mcp, sessao):
    mcp.resultados = {"analisar_risco": {"situacao": "ALERTA"}, "consultar_canais": {"total": 2}}
    ia = claude(
        [
            mensagem(
                [pedido_de_tool("t1", "analisar_risco", {"regiao": "Norte"}), pedido_de_tool("t2", "consultar_canais")],
                stop_reason="tool_use",
            ),
            mensagem([texto("Região Norte em alerta.")]),
        ]
    )

    eventos = await coletar(agente.conversar(sessao, "Risco no Norte?"))

    # O MCP recebeu as duas chamadas, com os argumentos certos.
    assert sorted(mcp.chamadas, key=lambda c: c[0]) == [("analisar_risco", {"regiao": "Norte"}), ("consultar_canais", {})]
    tipos = [e["type"] for e in eventos]
    assert tipos.count("tool") == 2 and tipos.count("tool_fim") == 2
    assert eventos[-1]["type"] == "fim" and eventos[-1]["uso"]["tools"] == 2 and eventos[-1]["uso"]["rodadas"] == 2

    # Os resultados voltam ao Claude TODOS numa única mensagem de usuário, com os ids certos.
    segunda = ia.chamadas[1]["messages"]
    assert [m["role"] for m in segunda] == ["user", "assistant", "user"]
    blocos = segunda[2]["content"]
    assert [b["tool_use_id"] for b in blocos] == ["t1", "t2"]
    assert blocos[0]["content"] == '{"situacao": "ALERTA"}'
    assert all(b["is_error"] is False for b in blocos)
    # A conversa guardada: pergunta, pedido de tools, resultados, resposta final.
    assert [m["role"] for m in sessao.mensagens] == ["user", "assistant", "user", "assistant"]


async def test_tool_que_devolve_erro_e_marcada_como_erro(claude, mcp, sessao):
    mcp.resultados = {"analisar_risco": {"erro": "Não foi possível consultar o backend.", "detalhe": "fora do ar"}}
    ia = claude(
        [
            mensagem([pedido_de_tool("t1", "analisar_risco")], stop_reason="tool_use"),
            mensagem([texto("Não consegui consultar os dados agora.")]),
        ]
    )

    eventos = await coletar(agente.conversar(sessao, "Risco?"))

    assert next(e for e in eventos if e["type"] == "tool_fim")["ok"] is False
    assert ia.chamadas[1]["messages"][-1]["content"][0]["is_error"] is True


async def test_resultado_muito_longo_e_cortado(claude, mcp, sessao, monkeypatch):
    monkeypatch.setattr(config, "MAX_RESULTADO_TOOL", 50)
    mcp.resultados = {"consultar_canais": {"itens": ["x" * 500]}}
    ia = claude(
        [mensagem([pedido_de_tool("t1", "consultar_canais")], stop_reason="tool_use"), mensagem([texto("ok")])]
    )

    await coletar(agente.conversar(sessao, "canais"))

    conteudo = ia.chamadas[1]["messages"][-1]["content"][0]["content"]
    assert conteudo.endswith("[resultado cortado por ser muito longo]")
    assert len(conteudo) < 120


async def test_conversa_continua_acrescentando_sem_editar_o_historico(claude, mcp, sessao):
    ia = claude([mensagem([texto("Primeira.")]), mensagem([texto("Segunda.")])])

    await coletar(agente.conversar(sessao, "pergunta 1"))
    primeiro_historico = list(sessao.mensagens)
    await coletar(agente.conversar(sessao, "pergunta 2"))

    # A segunda chamada começa exatamente com o histórico anterior (só acrescenta ao final).
    enviado = ia.chamadas[1]["messages"]
    assert enviado[: len(primeiro_historico)] == primeiro_historico
    assert enviado[-1] == {"role": "user", "content": "pergunta 2"}
    assert sessao.turnos == 2


async def test_prompt_do_sistema_e_tools_ficam_fixos_entre_perguntas(claude, mcp, sessao):
    ia = claude([mensagem([texto("a")]), mensagem([texto("b")])])
    await coletar(agente.conversar(sessao, "um"))
    await coletar(agente.conversar(sessao, "dois"))
    assert ia.chamadas[0]["system"] == ia.chamadas[1]["system"]
    assert ia.chamadas[0]["tools"] == ia.chamadas[1]["tools"]


async def test_recusa_do_modelo_nao_altera_a_conversa(claude, mcp, sessao):
    claude([mensagem([], stop_reason="refusal")])

    eventos = await coletar(agente.conversar(sessao, "algo"))

    assert eventos[-1] == {"type": "erro", "mensagem": "O assistente não pôde responder a essa pergunta."}
    assert sessao.mensagens == [] and sessao.turnos == 0


async def test_limite_de_rodadas(claude, mcp, sessao, monkeypatch):
    monkeypatch.setattr(config, "MAX_RODADAS", 2)
    claude([mensagem([pedido_de_tool(f"t{i}", "consultar_canais")], stop_reason="tool_use") for i in range(5)])

    eventos = await coletar(agente.conversar(sessao, "loop"))

    assert eventos[-1]["type"] == "erro" and "consultas demais" in eventos[-1]["mensagem"]
    assert sessao.mensagens == []


async def test_resposta_cortada_por_max_tokens(claude, mcp, sessao):
    claude([mensagem([texto("meio")], stop_reason="max_tokens")])
    eventos = await coletar(agente.conversar(sessao, "longo"))
    assert eventos[-1]["type"] == "erro" and "cortada" in eventos[-1]["mensagem"]


async def test_mcp_fora_do_ar(claude, mcp, sessao):
    claude([mensagem([texto("nunca chega")])])
    mcp.falha_ao_conectar = ConnectionError("recusada")

    eventos = await coletar(agente.conversar(sessao, "oi"))

    assert eventos == [
        {"type": "erro", "mensagem": f"Não foi possível conectar ao MCP Server ({config.MCP_URL}). Ele está rodando?"}
    ]


async def test_erro_de_conexao_embrulhado_em_grupo_de_excecoes(claude, mcp, sessao):
    claude([])
    mcp.falha_ao_conectar = ExceptionGroup("grupo", [ConnectionError("recusada")])
    eventos = await coletar(agente.conversar(sessao, "oi"))
    assert "Não foi possível conectar ao MCP Server" in eventos[0]["mensagem"]


async def test_chave_invalida_da_anthropic(claude, mcp, sessao):
    requisicao = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    erro = anthropic.AuthenticationError("invalid x-api-key", response=httpx2.Response(401, request=requisicao), body=None)
    claude([erro])

    eventos = await coletar(agente.conversar(sessao, "oi"))

    assert "chave da API da Anthropic é inválida" in eventos[-1]["mensagem"]
    assert "x-api-key" not in eventos[-1]["mensagem"]  # o detalhe técnico fica só no log
    assert sessao.mensagens == []


async def test_erro_da_api_dentro_de_grupo_de_excecoes(claude, mcp, sessao, monkeypatch):
    requisicao = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    limite = anthropic.RateLimitError("rate", response=httpx2.Response(429, request=requisicao), body=None)

    class MCPQueEmbrulha:
        async def __aenter__(self):
            raise ExceptionGroup("tg", [limite])

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(agente, "Client", lambda url: MCPQueEmbrulha())
    claude([])
    eventos = await coletar(agente.conversar(sessao, "oi"))
    assert "Limite de uso" in eventos[-1]["mensagem"]


async def test_fallback_de_recusa_e_enviado_quando_ligado(claude, mcp, sessao, monkeypatch):
    monkeypatch.setattr(config, "USAR_FALLBACK", True)
    ia = claude([mensagem([texto("ok")])])

    await coletar(agente.conversar(sessao, "oi"))

    chamada = ia.chamadas[0]
    assert chamada["_via"] == "beta"
    assert chamada["betas"] == ["server-side-fallback-2026-07-01"]
    assert chamada["fallbacks"] == "default"


async def test_conta_sem_o_recurso_de_fallback_segue_sem_ele(claude, mcp, sessao, monkeypatch):
    monkeypatch.setattr(config, "USAR_FALLBACK", True)
    ia = claude([erro_400("fallbacks is not enabled for this organization"), mensagem([texto("ok")])])

    eventos = await coletar(agente.conversar(sessao, "oi"))

    assert eventos[-1]["type"] == "fim"
    assert [c["_via"] for c in ia.chamadas] == ["beta", "messages"]


async def test_outro_erro_400_nao_e_escondido(claude, mcp, sessao, monkeypatch):
    monkeypatch.setattr(config, "USAR_FALLBACK", True)
    claude([erro_400("max_tokens: invalid")])
    eventos = await coletar(agente.conversar(sessao, "oi"))
    assert eventos[-1]["type"] == "erro"


async def test_cada_perfil_recebe_instrucoes_proprias(claude, mcp):
    from sessoes import Sessao

    ia = claude([mensagem([texto("a")]), mensagem([texto("b")])])
    await coletar(agente.conversar(Sessao(id="op", perfil="defesa_civil"), "oi"))
    await coletar(agente.conversar(Sessao(id="mo", perfil="cidadao"), "oi"))

    operador, morador = ia.chamadas[0]["system"], ia.chamadas[1]["system"]
    assert "operador da Defesa Civil" in operador and "morador da cidade" not in operador
    assert "morador da cidade" in morador and "193" in morador and "199" in morador
    # O que vale para todos vale nos dois: só dados das ferramentas e nada de ordens de evacuação.
    for instrucoes in (operador, morador):
        assert "Nunca invente" in instrucoes and "Não emita ordens de evacuação" in instrucoes
