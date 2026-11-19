"""O backend simulado imita o Spring Boot real, e o MCP entende o formato dele."""

import httpx
import pytest

from client.backend_client import ENDPOINTS, BackendClient, usar_backend
from simulador.backend_simulado import app
from tools.alertas import consultar_alertas
from tools.bueiros import consultar_bueiros
from tools.canais import analisar_fluxo_canal, consultar_canais
from tools.chuva import consultar_previsao_chuva
from tools.ocorrencias import consultar_ocorrencias
from tools.risco import analisar_risco, consultar_situacao_cidade
from tools.sensores import consultar_sensor, historico_sensor


@pytest.fixture
def simulador():
    usar_backend(BackendClient("http://simulador", timeout=5, transport=httpx.ASGITransport(app=app)))
    yield
    usar_backend(None)


async def test_todas_as_rotas_do_mcp_existem_no_simulador():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://simulador") as http:
        for nome, rota in ENDPOINTS.items():
            assert (await http.get(rota)).status_code == 200, nome


async def test_simulador_so_aceita_get():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://simulador") as http:
        assert (await http.post("/api/sensores", json={})).status_code == 405


async def test_campos_do_backend_real_sao_traduzidos(simulador):
    canal = (await consultar_canais())["canais"][0]  # o mais cheio
    assert (canal["nome"], canal["localizacao"], canal["vazaoEntrada"], canal["vazaoSaida"]) == (
        "Canal Norte", "Norte", 920, 640
    )
    assert canal["percentual"] == 87.0  # nivelAgua / capacidade
    previsao = (await consultar_previsao_chuva(regiao="Centro"))["previsoes"][0]
    assert (previsao["chuvaPrevista"], previsao["intensidade"]) == (80, "FORTE")
    bueiro = (await consultar_bueiros(status="OBSTRUIDO"))["bueiros"][0]
    assert bueiro["nivelObstrucao"] == 90


async def test_sensor_do_backend_real(simulador):
    sensor = await consultar_sensor(id=3)
    assert (sensor["codigo"], sensor["localizacao"], sensor["nivel"], sensor["status"]) == (
        "DRN-003 Praça Central", "Centro", 3.72, "CRITICO"
    )
    assert "aviso" not in sensor  # tem nível, então tem leitura
    assert (await consultar_sensor(id=99))["erro"] == "Sensor 99 não encontrado."


async def test_resumo_calculado_pelo_mcp(simulador):
    resumo = await consultar_situacao_cidade()
    assert resumo["situacaoGeral"] == "CRITICO"
    assert resumo["alertasAtivos"] == 4
    assert resumo["ocorrenciasAbertas"] == 3
    assert resumo["sensoresAtivos"] == 7


async def test_alertas_e_ocorrencias_filtrados_pelo_status(simulador):
    assert (await consultar_alertas())["total"] == 4
    assert (await consultar_alertas(apenas_ativos=False))["total"] == 5
    assert (await consultar_ocorrencias())["total"] == 3
    assert (await consultar_ocorrencias(status="TODAS"))["total"] == 4


async def test_analise_de_risco_usa_todas_as_fontes(simulador):
    analise = await analisar_risco()
    assert "erro" not in analise
    assert analise["fontesIndisponiveis"] == []
    assert analise["situacao"] in ("ALERTA", "CRITICO")
    assert analise["nivelConfianca"] == "ALTO"
    assert "Centro" in analise["areasMaisAfetadas"]


async def test_canal_norte_reproduz_o_exemplo_do_enunciado(simulador):
    resposta = await analisar_fluxo_canal(id=3)
    assert resposta["fluxo"]["resumo"] == "Entrada: 920 m³/h | Saída: 640 m³/h | Saldo: +280 m³/h"


async def test_historico_ainda_nao_existe_no_backend(simulador):
    resposta = await historico_sensor(id=1)
    assert resposta["erro"] == "O backend ainda não oferece o histórico de leituras."
