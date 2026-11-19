"""Tools dos sensores de drenagem: lista, detalhe e histórico com tendência."""

from typing import Annotated, Any

from pydantic import Field

from client.backend_client import RecursoNaoEncontrado, obter_backend
from models.schemas import (
    LeituraSensor,
    PeriodoHistorico,
    Sensor,
    StatusMonitoramento,
    contar_por,
    ordenar_por_percentual,
    resposta_erro,
    resposta_lista,
    validar,
    validar_lista,
)
from services.analise_risco import analisar_tendencia

# Limite de leituras devolvidas à IA (a tendência é calculada sobre todas).
MAXIMO_DE_LEITURAS = 48

IdSensor = Annotated[int, Field(ge=1, description="Id numérico do sensor (veja consultar_sensores).")]


async def consultar_sensores(
    status: Annotated[
        StatusMonitoramento | None,
        Field(description="Filtra pelo status do sensor. Omita para listar todos."),
    ] = None,
) -> dict[str, Any]:
    """Lista os sensores de drenagem com nível, capacidade, percentual, vazões de entrada/saída e status.

    Pode filtrar por status (NORMAL, ATENCAO, ALERTA, CRITICO), por exemplo
    consultar_sensores(status="CRITICO") para "Quais sensores estão críticos?".
    Os sensores vêm do maior para o menor percentual de ocupação, e resumoPorStatus
    traz a contagem de todos os sensores da cidade.
    """
    sensores = validar_lista(Sensor, await obter_backend().listar_sensores())
    resumo = contar_por([sensor.status for sensor in sensores])
    if status:
        sensores = [sensor for sensor in sensores if sensor.status == status]
    return resposta_lista(
        "sensores", ordenar_por_percentual(sensores), filtros={"status": status}, resumoPorStatus=resumo
    )


async def consultar_sensor(id: IdSensor) -> dict[str, Any]:
    """Consulta um sensor específico: código, localização, nível, capacidade, percentual, entrada, saída, status e última atualização."""
    try:
        dados = await obter_backend().obter_sensor(id)
    except RecursoNaoEncontrado:
        return resposta_erro(f"Sensor {id} não encontrado.", "Confira o id com a ferramenta consultar_sensores.")

    sensor = validar(Sensor, dados)
    resposta = sensor.model_dump()
    if sensor.nivel is None and sensor.percentual is None:
        resposta["aviso"] = "Não foi possível obter a leitura atual do sensor."
    return resposta


async def historico_sensor(
    id: IdSensor,
    periodo: Annotated[PeriodoHistorico, Field(description="Janela de tempo do histórico.")] = "24h",
) -> dict[str, Any]:
    """Consulta o histórico de leituras de um sensor e indica a tendência (aumento, redução, estabilidade ou dados insuficientes).

    Use para perguntas como "O nível do sensor Norte está subindo?". A tendência
    descreve as leituras passadas e não é uma previsão.
    """
    backend = obter_backend()
    try:
        await backend.obter_sensor(id)
    except RecursoNaoEncontrado:
        return resposta_erro(f"Sensor {id} não encontrado.", "Confira o id com a ferramenta consultar_sensores.")
    try:
        dados = await backend.historico_sensor(id, periodo)
    except RecursoNaoEncontrado:
        return resposta_erro(
            "O backend ainda não oferece o histórico de leituras.",
            "Falta a rota GET /api/sensores/{id}/historico no Spring Boot; sem ela não há como avaliar a tendência.",
        )

    leituras = validar_lista(LeituraSensor, dados)
    if all(leitura.dataHora for leitura in leituras):
        leituras.sort(key=lambda leitura: leitura.dataHora)

    # Prefere o percentual (comparável entre sensores); usa o nível se faltar percentual.
    grandeza = "percentual" if leituras and all(l.percentual is not None for l in leituras) else "nivel"
    tendencia = analisar_tendencia([getattr(leitura, grandeza) for leitura in leituras])

    amostra = _amostrar(leituras, MAXIMO_DE_LEITURAS)
    resposta = {
        "sensorId": id,
        "periodo": periodo,
        "totalLeituras": len(leituras),
        "leiturasRetornadas": len(amostra),
        "grandezaAnalisada": grandeza,
        "tendencia": tendencia.model_dump(),
        "leituras": [leitura.model_dump() for leitura in amostra],
    }
    if not leituras:
        resposta["aviso"] = f"Nenhuma leitura encontrada para o sensor {id} no período de {periodo}."
    return resposta


def _amostrar(itens: list[Any], limite: int) -> list[Any]:
    """Escolhe até `limite` itens espaçados por igual, mantendo o primeiro e o último."""
    if len(itens) <= limite:
        return itens
    passo = (len(itens) - 1) / (limite - 1)
    return [itens[round(i * passo)] for i in range(limite)]


FERRAMENTAS = [consultar_sensores, consultar_sensor, historico_sensor]
