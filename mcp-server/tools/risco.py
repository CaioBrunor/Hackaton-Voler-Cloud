"""Tools de visão geral: resumo da cidade e análise de risco combinada."""

import asyncio
from typing import Annotated, Any

from pydantic import Field

from client.backend_client import RecursoNaoEncontrado, obter_backend
from models.schemas import (
    Alerta,
    AreaRisco,
    Barragem,
    Bueiro,
    Canal,
    DadosCidade,
    ErroConsulta,
    Ocorrencia,
    PrevisaoChuva,
    ResumoCidade,
    Sensor,
    esta_ativo,
    resposta_erro,
    validar,
    validar_lista,
)
from services.analise_risco import avaliar_risco, resumir_cidade


async def consultar_situacao_cidade() -> dict[str, Any]:
    """Consulta o resumo atual da situação da cidade, incluindo sensores, canais, barragens, alertas e ocorrências.

    Retorna a situação geral (NORMAL, ATENCAO, ALERTA ou CRITICO) e os totais de
    sensores ativos, sensores/canais/barragens em alerta, alertas ativos e
    ocorrências abertas. Use como primeiro passo para "Qual a situação atual da cidade?".
    """
    backend = obter_backend()
    try:
        return validar(ResumoCidade, await backend.resumo_cidade()).model_dump()
    except RecursoNaoEncontrado:
        pass  # o backend não tem a rota de resumo: o MCP calcula a partir das listas

    sensores, canais, barragens, alertas, ocorrencias = await asyncio.gather(
        backend.listar_sensores(),
        backend.listar_canais(),
        backend.listar_barragens(),
        backend.listar_alertas(),
        backend.listar_ocorrencias(),
    )
    return resumir_cidade(
        validar_lista(Sensor, sensores),
        validar_lista(Canal, canais),
        validar_lista(Barragem, barragens),
        validar_lista(Alerta, alertas),
        validar_lista(Ocorrencia, ocorrencias),
    )


async def analisar_risco(
    regiao: Annotated[
        str | None,
        Field(description="Limita a análise a uma região (ex.: 'Norte', 'Centro'). Omita para a cidade inteira."),
    ] = None,
) -> dict[str, Any]:
    """Analisa o risco de alagamento combinando previsão de chuva, sensores, canais, bueiros, barragens, áreas de risco e alertas ativos.

    Retorna a situação (NORMAL, ATENCAO, ALERTA ou CRITICO), o nível de confiança
    dos dados, os principais fatores, as áreas mais afetadas e uma recomendação de
    monitoramento. A análise usa regras fixas e serve de apoio à decisão: não
    emite ordens de evacuação nem decisões operacionais. Se alguma fonte estiver
    fora do ar, a análise usa só os dados obtidos e lista as fontes indisponíveis.
    """
    backend = obter_backend()
    # Fonte -> (consulta ao backend, modelo usado para interpretar a resposta).
    consultas = {
        "previsao_chuva": (backend.previsao_chuva(), PrevisaoChuva),
        "sensores": (backend.listar_sensores(), Sensor),
        "canais": (backend.listar_canais(), Canal),
        "bueiros": (backend.listar_bueiros(), Bueiro),
        "barragens": (backend.listar_barragens(), Barragem),
        "areas_risco": (backend.listar_areas_risco(), AreaRisco),
        "alertas": (backend.listar_alertas(), Alerta),
    }
    # As sete consultas rodam em paralelo; a falha de uma não derruba as outras.
    respostas = await asyncio.gather(*(consulta for consulta, _ in consultas.values()), return_exceptions=True)

    obtidos: dict[str, list[Any]] = {}
    indisponiveis: list[str] = []
    for (fonte, (_, modelo)), resposta in zip(consultas.items(), respostas):
        if isinstance(resposta, ErroConsulta):
            indisponiveis.append(fonte)
            continue
        if isinstance(resposta, BaseException):
            raise resposta  # erro de programação: não deve ser escondido como "fonte indisponível"
        try:
            obtidos[fonte] = validar_lista(modelo, resposta)
        except ErroConsulta:
            indisponiveis.append(fonte)

    if not obtidos:
        return resposta_erro(
            "Não foi possível consultar o backend.",
            "Nenhuma fonte de dados respondeu; a análise não foi feita para não usar dados inventados.",
        )

    dados = DadosCidade(
        previsoes=obtidos.get("previsao_chuva", []),
        sensores=obtidos.get("sensores", []),
        canais=obtidos.get("canais", []),
        bueiros=obtidos.get("bueiros", []),
        barragens=obtidos.get("barragens", []),
        areas_risco=obtidos.get("areas_risco", []),
        alertas=[alerta for alerta in obtidos.get("alertas", []) if esta_ativo(alerta.situacao)],
        fontes_consultadas=list(obtidos),
        fontes_indisponiveis=indisponiveis,
    )
    return avaliar_risco(dados, regiao).model_dump()


FERRAMENTAS = [consultar_situacao_cidade, analisar_risco]
