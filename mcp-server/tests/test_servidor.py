"""Servidor MCP completo, acessado por um cliente MCP de verdade (em memória)."""

import json
import logging

from mcp import Client

from main import criar_servidor
from tools.sensores import consultar_sensores
from utils.logs import _parametros_para_log, monitorar

TOOLS_ESPERADAS = {
    "consultar_situacao_cidade",
    "consultar_previsao_chuva",
    "consultar_sensores",
    "consultar_sensor",
    "historico_sensor",
    "consultar_canais",
    "analisar_fluxo_canal",
    "consultar_bueiros",
    "consultar_barragens",
    "consultar_areas_risco",
    "consultar_alertas",
    "consultar_ocorrencias",
    "analisar_risco",
}

RESOURCES_ESPERADOS = {
    "cidade://situacao-atual",
    "cidade://alertas-ativos",
    "cidade://areas-risco",
    "cidade://sensores",
    "cidade://barragens",
}


async def test_ia_descobre_todas_as_tools_somente_leitura():
    async with Client(criar_servidor()) as cliente:
        tools = (await cliente.list_tools()).tools
    assert {tool.name for tool in tools} == TOOLS_ESPERADAS
    for tool in tools:
        assert tool.description, tool.name
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.destructive_hint is False, tool.name


async def test_parametros_aparecem_com_valores_permitidos():
    async with Client(criar_servidor()) as cliente:
        tools = {tool.name: tool for tool in (await cliente.list_tools()).tools}
    status = tools["consultar_sensores"].input_schema["properties"]["status"]
    assert {"enum": ["NORMAL", "ATENCAO", "ALERTA", "CRITICO"], "type": "string"} in status["anyOf"]
    assert tools["consultar_sensor"].input_schema["required"] == ["id"]


async def test_chamada_de_tool_pelo_protocolo(backend):
    async with Client(criar_servidor()) as cliente:
        resultado = await cliente.call_tool("consultar_sensores", {"status": "CRITICO"})
    assert not resultado.is_error
    assert resultado.structured_content["total"] == 1
    assert json.loads(resultado.content[0].text)["sensores"][0]["codigo"] == "DRN-003"


async def test_parametro_invalido_e_recusado(backend):
    async with Client(criar_servidor()) as cliente:
        resultado = await cliente.call_tool("consultar_sensores", {"status": "QUALQUER"})
    assert resultado.is_error
    assert backend.chamadas == []


async def test_backend_fora_do_ar_pelo_protocolo(backend_desligado):
    async with Client(criar_servidor()) as cliente:
        resultado = await cliente.call_tool("consultar_situacao_cidade", {})
    assert resultado.structured_content == {
        "erro": "Não foi possível consultar o backend.",
        "detalhe": "Serviço temporariamente indisponível.",
    }


async def test_resources_da_cidade(backend):
    async with Client(criar_servidor()) as cliente:
        uris = {str(recurso.uri) for recurso in (await cliente.list_resources()).resources}
        conteudo = await cliente.read_resource("cidade://sensores")
    assert uris == RESOURCES_ESPERADOS
    assert conteudo.contents[0].mime_type == "application/json"
    assert json.loads(conteudo.contents[0].text)["total"] == 4


async def test_log_registra_ferramenta_parametros_resultado_e_tempo(backend, caplog):
    caplog.set_level(logging.INFO, logger="anti_enchente")
    await monitorar(consultar_sensores)(status="CRITICO")
    linha = caplog.records[-1].getMessage()
    assert "ferramenta=consultar_sensores" in linha
    assert 'parametros={"status": "CRITICO"}' in linha
    assert "resultado=sucesso" in linha
    assert "tempo=" in linha


async def test_log_de_erro(backend_desligado, caplog):
    caplog.set_level(logging.INFO, logger="anti_enchente")
    await monitorar(consultar_sensores)()
    registro = caplog.records[-1]
    assert registro.levelno == logging.WARNING
    assert "resultado=erro (Não foi possível consultar o backend." in registro.getMessage()


def test_log_nao_registra_dados_sensiveis():
    texto = _parametros_para_log({"token": "abc123", "regiao": "Norte", "mensagem": "x" * 500})
    assert "abc123" not in texto
    assert '"token": "***"' in texto
    assert len(texto) < 200
