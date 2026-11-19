"""Tool dos bueiros monitorados."""

from typing import Annotated, Any

from pydantic import Field

from client.backend_client import obter_backend
from models.schemas import Bueiro, contar_por, contem, normalizar, ordenar_por_gravidade, resposta_lista, validar_lista


async def consultar_bueiros(
    status: Annotated[
        str | None,
        Field(description="Situação do bueiro, ex.: NORMAL, PARCIALMENTE_OBSTRUIDO, OBSTRUIDO. Omita para todos."),
    ] = None,
    regiao: Annotated[
        str | None,
        Field(description="Região ou bairro para filtrar (ex.: 'Norte'). Omita para todas."),
    ] = None,
) -> dict[str, Any]:
    """Lista os bueiros monitorados com localização, região e situação.

    Use consultar_bueiros(status="OBSTRUIDO") para "Existem bueiros obstruídos?".
    Para saber se há bueiro obstruído perto de uma área de risco, combine com
    consultar_areas_risco e compare as regiões. resumoPorStatus traz a contagem de
    todos os bueiros da cidade.
    """
    bueiros = validar_lista(Bueiro, await obter_backend().listar_bueiros())
    resumo = contar_por([bueiro.status for bueiro in bueiros])
    if status:
        bueiros = [bueiro for bueiro in bueiros if bueiro.status == normalizar(status)]
    if regiao:
        bueiros = [b for b in bueiros if contem(b.regiao, regiao) or contem(b.localizacao, regiao)]
    return resposta_lista(
        "bueiros",
        ordenar_por_gravidade(bueiros, "status"),
        filtros={"status": status, "regiao": regiao},
        resumoPorStatus=resumo,
    )


FERRAMENTAS = [consultar_bueiros]
