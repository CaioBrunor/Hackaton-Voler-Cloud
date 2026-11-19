"""Tool das barragens."""

from typing import Annotated, Any

from pydantic import Field

from client.backend_client import obter_backend
from models.schemas import (
    Barragem,
    StatusMonitoramento,
    contar_por,
    ordenar_por_percentual,
    resposta_lista,
    validar_lista,
)


async def consultar_barragens(
    status: Annotated[
        StatusMonitoramento | None,
        Field(description="Filtra pelo status da barragem. Omita para listar todas."),
    ] = None,
) -> dict[str, Any]:
    """Lista as barragens com nome, localização, capacidade, volume atual, percentual, entrada, saída, nível e status.

    As barragens vêm da mais cheia para a menos cheia: a primeira da lista responde
    "Qual barragem está com maior nível/percentual?". saldoVazao é entrada menos saída.
    """
    barragens = validar_lista(Barragem, await obter_backend().listar_barragens())
    resumo = contar_por([barragem.status for barragem in barragens])
    if status:
        barragens = [barragem for barragem in barragens if barragem.status == status]
    return resposta_lista(
        "barragens", ordenar_por_percentual(barragens), filtros={"status": status}, resumoPorStatus=resumo
    )


FERRAMENTAS = [consultar_barragens]
