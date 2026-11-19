"""Regras de services/analise_risco.py, testadas sem backend."""

from models.schemas import AreaRisco, Bueiro, Canal, DadosCidade, PrevisaoChuva, Sensor
from services.analise_risco import analisar_fluxo, analisar_tendencia, avaliar_risco

TODAS_AS_FONTES = ["previsao_chuva", "sensores", "canais", "bueiros", "barragens", "areas_risco", "alertas"]


def _dados(**kwargs) -> DadosCidade:
    kwargs.setdefault("sensores", [Sensor(codigo="S-1", percentual=40, status="NORMAL")])
    kwargs.setdefault("fontes_consultadas", TODAS_AS_FONTES)
    return DadosCidade(**kwargs)


# ---------------------------------------------------------------- tendência


def test_tendencia_de_aumento_do_enunciado():
    analise = analisar_tendencia([40, 52, 67, 81])
    assert analise.tendencia == "AUMENTO"
    assert analise.descricao == "O nível do sensor apresentou tendência de aumento nas últimas leituras."
    assert analise.variacao == 41


def test_tendencia_de_reducao():
    assert analisar_tendencia([81, 67, 52, 40]).tendencia == "REDUCAO"


def test_oscilacao_pequena_e_estabilidade():
    assert analisar_tendencia([50, 51, 49, 50, 51]).tendencia == "ESTABILIDADE"


def test_serie_zerada_e_estabilidade():
    assert analisar_tendencia([0, 0, 0]).tendencia == "ESTABILIDADE"


def test_poucas_leituras_sao_dados_insuficientes():
    analise = analisar_tendencia([40, 52])
    assert analise.tendencia == "DADOS_INSUFICIENTES"
    assert analise.variacao is None


def test_leituras_vazias_sao_ignoradas():
    analise = analisar_tendencia([40, None, 52, 67])
    assert analise.tendencia == "AUMENTO"
    assert analise.leiturasAnalisadas == 3


# ---------------------------------------------------------------- fluxo


def test_fluxo_com_entrada_maior_que_saida_indica_acumulo_potencial():
    fluxo = analisar_fluxo(920, 640)
    assert fluxo.saldo == 280
    assert fluxo.situacaoFluxo == "ACUMULO_POTENCIAL"
    assert fluxo.resumo == "Entrada: 920 m³/h | Saída: 640 m³/h | Saldo: +280 m³/h"
    assert "acúmulo potencial" in fluxo.interpretacao
    assert "não permite afirmar que haverá enchente" in fluxo.observacao


def test_fluxo_com_saida_maior_que_entrada():
    fluxo = analisar_fluxo(500, 700)
    assert fluxo.situacaoFluxo == "ESCOAMENTO"
    assert fluxo.resumo.endswith("Saldo: -200 m³/h")


def test_fluxo_equilibrado():
    assert analisar_fluxo(600, 600).situacaoFluxo == "EQUILIBRIO"


def test_fluxo_sem_leitura_nao_inventa_saldo():
    fluxo = analisar_fluxo(None, 640)
    assert fluxo.situacaoFluxo == "DADOS_INSUFICIENTES"
    assert fluxo.saldo is None


# ---------------------------------------------------------------- risco


def test_cidade_sem_indicadores_fora_do_normal():
    analise = avaliar_risco(_dados(previsoes=[PrevisaoChuva(regiao="Centro", intensidade="FRACA")]))
    assert analise.situacao == "NORMAL"
    assert analise.nivelConfianca == "ALTO"
    assert analise.pontuacao == 0
    assert analise.principaisFatores == ["Nenhum indicador fora da normalidade nos dados consultados."]
    assert analise.recomendacao == "Manter o monitoramento de rotina."


def test_exemplo_do_enunciado_resulta_em_alerta():
    analise = avaliar_risco(
        _dados(
            previsoes=[PrevisaoChuva(regiao="Norte", chuvaPrevista=80, periodo="3 horas", intensidade="FORTE")],
            canais=[
                Canal(nome="Canal Norte", regiao="Norte", percentual=87, vazaoEntrada=920, vazaoSaida=640, status="ALERTA")
            ],
            areas_risco=[AreaRisco(regiao="Região Norte", populacaoEstimada=12000, nivelRisco="ALTO")],
        )
    )
    assert analise.situacao == "ALERTA"
    assert analise.principaisFatores[:3] == [
        "Previsão de chuva forte para Norte (80 mm em 3 horas)",
        "Canal Norte com 87% da capacidade (status ALERTA)",
        "Área de risco ALTO em Região Norte (população estimada: 12.000) com indicadores em alerta",
    ]
    assert "Canal Norte: entrada de água superior à saída (+280 m³/h)" in analise.principaisFatores
    assert analise.areasMaisAfetadas == ["Norte"]
    assert analise.criterios["fluxo"] == 1
    assert analise.criterios["vulnerabilidade"] == 1


def test_um_indicador_critico_eleva_para_no_minimo_alerta():
    analise = avaliar_risco(_dados(canais=[Canal(nome="Canal Leste", percentual=95)]))
    assert analise.pontuacao == 3
    assert analise.situacao == "ALERTA"


def test_varios_indicadores_criticos_resultam_em_critico():
    analise = avaliar_risco(
        _dados(
            previsoes=[PrevisaoChuva(regiao="Centro", intensidade="MUITO_FORTE")],
            sensores=[Sensor(codigo="S-1", regiao="Centro", percentual=96, status="CRITICO")],
            canais=[Canal(nome="Canal Centro", regiao="Centro", percentual=92, status="CRITICO")],
        )
    )
    assert analise.situacao == "CRITICO"


def test_recomendacao_nunca_e_ordem_de_evacuacao():
    analise = avaliar_risco(
        _dados(
            previsoes=[PrevisaoChuva(regiao="Centro", intensidade="MUITO_FORTE")],
            sensores=[Sensor(codigo="S-1", regiao="Centro", percentual=99, status="CRITICO")],
            canais=[Canal(nome="Canal Centro", regiao="Centro", percentual=99, status="CRITICO")],
        )
    )
    assert analise.situacao == "CRITICO"
    assert "evacu" not in analise.recomendacao.lower()
    assert "não constitui ordem de evacuação" in analise.observacao


def test_bueiro_obstruido_sozinho_nao_passa_de_atencao():
    analise = avaliar_risco(_dados(bueiros=[Bueiro(codigo="BU-1", localizacao="Rua A", status="OBSTRUIDO")]))
    assert analise.criterios["bueiros"] == 2
    assert analise.situacao == "ATENCAO"
    assert "Verificar a desobstrução dos bueiros indicados." in analise.recomendacao


def test_fonte_indisponivel_reduz_confianca_e_aparece_na_resposta():
    analise = avaliar_risco(_dados(fontes_indisponiveis=["bueiros"]))
    assert analise.nivelConfianca == "MEDIO"
    assert analise.fontesIndisponiveis == ["bueiros"]
    assert "bueiros" in analise.observacao


def test_tres_fontes_indisponiveis_deixam_confianca_baixa():
    analise = avaliar_risco(_dados(fontes_indisponiveis=["bueiros", "alertas", "barragens"]))
    assert analise.nivelConfianca == "BAIXO"


def test_sem_leituras_de_sensores_canais_ou_barragens_confianca_baixa():
    assert avaliar_risco(_dados(sensores=[])).nivelConfianca == "BAIXO"


def test_filtro_por_regiao_ignora_outras_regioes():
    dados = _dados(
        sensores=[
            Sensor(codigo="S-N", regiao="Norte", percentual=95, status="CRITICO"),
            Sensor(codigo="S-S", regiao="Sul", percentual=30, status="NORMAL"),
        ]
    )
    assert avaliar_risco(dados).situacao == "ALERTA"
    sul = avaliar_risco(dados, regiao="Sul")
    assert sul.situacao == "NORMAL"
    assert sul.regiaoAnalisada == "Sul"


def test_endereco_de_bueiro_e_reconhecido_como_a_regiao_conhecida():
    analise = avaliar_risco(
        _dados(
            previsoes=[PrevisaoChuva(regiao="Norte", intensidade="FORTE")],
            areas_risco=[AreaRisco(regiao="Norte", nivelRisco="ALTO")],
            bueiros=[Bueiro(codigo="BU-1", localizacao="Av. Beira Rio, 180 - Norte", status="OBSTRUIDO")],
        )
    )
    # O bueiro (endereço) soma na região "Norte"; não aparece uma região chamada "Av. Beira Rio, 180 - Norte".
    assert analise.areasMaisAfetadas == ["Norte"]
