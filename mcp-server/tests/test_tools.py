"""Tools chamadas diretamente, com o backend simulado de conftest.py."""

from tools.alertas import consultar_alertas
from tools.areas_risco import consultar_areas_risco
from tools.barragens import consultar_barragens
from tools.bueiros import consultar_bueiros
from tools.canais import analisar_fluxo_canal, consultar_canais
from tools.chuva import consultar_previsao_chuva
from tools.ocorrencias import consultar_ocorrencias
from tools.risco import analisar_risco, consultar_situacao_cidade
from tools.sensores import consultar_sensor, consultar_sensores, historico_sensor
from utils.logs import monitorar

BACKEND_FORA_DO_AR = {"erro": "Não foi possível consultar o backend.", "detalhe": "Serviço temporariamente indisponível."}


async def test_resumo_calculado_quando_o_backend_nao_tem_a_rota(backend):
    del backend.rotas["/api/dashboard/resumo"]
    resumo = await consultar_situacao_cidade()
    assert resumo["situacaoGeral"] == "CRITICO"  # DRN-003 está crítico
    assert resumo["alertasAtivos"] == 2
    assert resumo["ocorrenciasAbertas"] == 3
    assert resumo["sensoresAtivos"] == 3
    assert "Calculado pelo MCP" in resumo["fonte"]


async def test_historico_quando_o_backend_nao_tem_a_rota(backend):
    del backend.rotas["/api/sensores/1/historico"]
    resposta = await historico_sensor(id=1)
    assert resposta["erro"] == "O backend ainda não oferece o histórico de leituras."


async def test_situacao_cidade(backend):
    resumo = await consultar_situacao_cidade()
    assert resumo["situacaoGeral"] == "ALERTA"
    assert resumo["sensoresAtivos"] == 24
    assert resumo["ocorrenciasAbertas"] == 2


async def test_previsao_de_chuva_por_regiao(backend):
    resposta = await consultar_previsao_chuva(regiao="centro")
    assert resposta["total"] == 1
    assert resposta["previsoes"][0]["intensidade"] == "FORTE"
    assert resposta["haPrevisaoChuvaForte"] is True


async def test_previsao_de_regiao_inexistente_informa_regioes_disponiveis(backend):
    resposta = await consultar_previsao_chuva(regiao="Leste")
    assert resposta["total"] == 0
    assert "Nenhuma previsão encontrada" in resposta["mensagem"]
    assert resposta["regioesDisponiveis"] == ["Centro", "Norte", "Sul"]


async def test_sensores_criticos_com_status_normalizado(backend):
    resposta = await consultar_sensores(status="CRITICO")
    assert [s["codigo"] for s in resposta["sensores"]] == ["DRN-003"]
    assert resposta["resumoPorStatus"] == {"ALERTA": 1, "NORMAL": 2, "CRITICO": 1}


async def test_sensores_do_mais_cheio_para_o_sem_leitura(backend):
    resposta = await consultar_sensores()
    assert [s["codigo"] for s in resposta["sensores"]] == ["DRN-003", "DRN-001", "DRN-002", "DRN-004"]


async def test_consultar_sensor_traz_todos_os_campos_pedidos(backend):
    sensor = await consultar_sensor(id=1)
    for campo in ("codigo", "localizacao", "nivel", "capacidade", "percentual",
                  "vazaoEntrada", "vazaoSaida", "status", "ultimaAtualizacao"):  # fmt: skip
        assert sensor[campo] is not None, campo
    assert sensor["saldoVazao"] == 280
    assert "aviso" not in sensor


async def test_sensor_sem_leitura_avisa_em_vez_de_inventar(backend):
    sensor = await consultar_sensor(id=4)
    assert sensor["nivel"] is None
    assert sensor["aviso"] == "Não foi possível obter a leitura atual do sensor."


async def test_sensor_inexistente(backend):
    resposta = await consultar_sensor(id=99)
    assert resposta["erro"] == "Sensor 99 não encontrado."


async def test_historico_ordena_leituras_e_aponta_tendencia(backend):
    resposta = await historico_sensor(id=1, periodo="24h")
    assert [l["percentual"] for l in resposta["leituras"]] == [40, 52, 67, 81]
    assert resposta["tendencia"]["tendencia"] == "AUMENTO"
    assert resposta["grandezaAnalisada"] == "percentual"
    assert ("GET", "http://backend.teste/api/sensores/1/historico?periodo=24h") in backend.chamadas


async def test_historico_longo_e_reduzido_para_a_ia(backend):
    backend.rotas["/api/sensores/1/historico"] = [
        {"dataHora": f"2026-11-19T{minuto // 60:02d}:{minuto % 60:02d}:00", "percentual": 40 + minuto / 30}
        for minuto in range(0, 1440, 5)
    ]
    resposta = await historico_sensor(id=1)
    assert resposta["totalLeituras"] == 288
    assert resposta["leiturasRetornadas"] == 48
    assert resposta["leituras"][-1]["dataHora"] == "2026-11-19T23:55:00"
    assert resposta["tendencia"]["leiturasAnalisadas"] == 288


async def test_canais_acima_de_80_por_cento(backend):
    resposta = await consultar_canais(percentual_minimo=80)
    assert [c["nome"] for c in resposta["canais"]] == ["Canal Norte"]
    canal = resposta["canais"][0]
    # O backend mandou "entrada"/"saida"/"situacao"; a IA recebe sempre o mesmo formato.
    assert (canal["vazaoEntrada"], canal["vazaoSaida"], canal["status"]) == (920, 640, "ALERTA")
    assert resposta["canaisComEntradaMaiorQueSaida"] == ["Canal Norte"]


async def test_analisar_fluxo_canal(backend):
    resposta = await analisar_fluxo_canal(id=3)
    assert resposta["canal"]["nome"] == "Canal Norte"
    assert resposta["fluxo"]["saldo"] == 280
    assert resposta["fluxo"]["situacaoFluxo"] == "ACUMULO_POTENCIAL"


async def test_bueiros_obstruidos_aceita_acento_e_minusculas(backend):
    resposta = await consultar_bueiros(status="obstruído")
    assert [b["codigo"] for b in resposta["bueiros"]] == ["BU-101"]
    parciais = await consultar_bueiros(status="PARCIALMENTE_OBSTRUIDO")
    assert [b["codigo"] for b in parciais["bueiros"]] == ["BU-102"]


async def test_bueiros_por_regiao(backend):
    resposta = await consultar_bueiros(regiao="Região Norte")
    assert [b["codigo"] for b in resposta["bueiros"]] == ["BU-101"]


async def test_barragens_da_mais_cheia_com_percentual_calculado(backend):
    resposta = await consultar_barragens()
    primeira = resposta["barragens"][0]
    assert primeira["nome"] == "Barragem Serra Azul"
    assert primeira["percentual"] == 91.0
    assert primeira["saldoVazao"] == 300


async def test_areas_de_risco_com_nomes_alternativos_do_backend(backend):
    resposta = await consultar_areas_risco(nivel="CRITICO")
    [area] = resposta["areas"]
    assert (area["regiao"], area["populacaoEstimada"], area["nivelRisco"], area["situacaoAtual"]) == (
        "Centro", 8000, "CRITICO", "Em monitoramento"
    )


async def test_areas_da_mais_grave_para_a_menos_grave(backend):
    resposta = await consultar_areas_risco()
    assert [a["regiao"] for a in resposta["areas"]] == ["Centro", "Região Norte", "Sul"]
    assert resposta["populacaoEstimadaTotal"] == 23000


async def test_alertas_ativos_sao_filtrados_pelo_mcp(backend):
    ativos = await consultar_alertas()
    assert ativos["total"] == 2  # o alerta ENCERRADO fica de fora
    assert ativos["alertas"][0]["id"] == 2  # mais recente primeiro
    todos = await consultar_alertas(apenas_ativos=False)
    assert todos["total"] == 3
    assert {url for _, url in backend.chamadas} == {"http://backend.teste/api/alertas"}


async def test_ocorrencias_abertas_sao_as_nao_encerradas(backend):
    resposta = await consultar_ocorrencias()
    # ABERTA e EM_ATENDIMENTO entram; ENCERRADA fica de fora. Mais prioritária primeiro.
    assert [o["id"] for o in resposta["ocorrencias"]] == [2, 1, 4]  # 1 e 4: mesma prioridade, a 1 é mais recente
    assert backend.chamadas[-1][1].endswith("/api/ocorrencias")


async def test_ocorrencias_por_outro_status_e_todas(backend):
    em_atendimento = await consultar_ocorrencias(status="em atendimento")
    assert [o["id"] for o in em_atendimento["ocorrencias"]] == [4]
    todas = await consultar_ocorrencias(status="TODAS")
    assert todas["total"] == 4


async def test_analisar_risco_com_todas_as_fontes(backend):
    analise = await analisar_risco()
    assert analise["situacao"] == "CRITICO"
    assert analise["nivelConfianca"] == "ALTO"
    assert analise["areasMaisAfetadas"] == ["Norte", "Centro", "Oeste"]
    assert analise["fontesIndisponiveis"] == []
    assert len(analise["fontesConsultadas"]) == 7


async def test_analisar_risco_segue_com_fonte_fora_do_ar(backend):
    backend.fora_do_ar.add("/api/bueiros")
    analise = await analisar_risco()
    assert analise["fontesIndisponiveis"] == ["bueiros"]
    assert analise["nivelConfianca"] == "MEDIO"
    assert analise["criterios"]["bueiros"] == 0


async def test_analisar_risco_de_uma_regiao(backend):
    analise = await analisar_risco(regiao="Sul")
    assert analise["situacao"] == "NORMAL"
    assert analise["regiaoAnalisada"] == "Sul"


async def test_analisar_risco_sem_nenhuma_fonte_nao_inventa_analise(backend_desligado):
    analise = await analisar_risco()
    assert analise["erro"] == "Não foi possível consultar o backend."


async def test_backend_fora_do_ar_vira_erro_compreensivel(backend_desligado):
    assert await monitorar(consultar_sensores)() == BACKEND_FORA_DO_AR
    assert await monitorar(consultar_situacao_cidade)() == BACKEND_FORA_DO_AR


async def test_backend_lento_informa_o_tempo_limite(backend_lento):
    resposta = await monitorar(consultar_canais)()
    assert resposta["detalhe"] == "O backend não respondeu em 5 segundos."


async def test_dados_em_formato_inesperado(backend):
    backend.rotas["/api/sensores"] = [{"codigo": "DRN-9", "percentual": "muito alto"}]
    resposta = await monitorar(consultar_sensores)()
    assert resposta["erro"] == "O backend retornou dados em formato inesperado."
    assert "percentual" in resposta["detalhe"]


async def test_mcp_so_faz_requisicoes_get(backend):
    await analisar_risco()
    await consultar_sensor(id=1)
    await consultar_ocorrencias(status="TODAS")
    assert backend.chamadas
    assert {metodo for metodo, _ in backend.chamadas} == {"GET"}
