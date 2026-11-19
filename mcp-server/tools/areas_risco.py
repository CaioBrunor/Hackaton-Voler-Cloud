"""Tool das áreas de risco."""

from typing import Annotated, Any

from pydantic import Field

from client.backend_client import obter_backend
from models.schemas import AreaRisco, NivelRisco, contar_por, gravidade, resposta_lista, validar_lista


async def consultar_areas_risco(
    nivel: Annotated[
        NivelRisco | None,
        Field(description="Filtra pelo nível de risco da área. Omita para listar todas."),
    ] = None,
) -> dict[str, Any]:
    """Lista as áreas de risco com região, população estimada, nível de risco (BAIXO, MEDIO, ALTO, CRITICO) e situação atual.

    As áreas vêm da mais grave para a menos grave (e, no mesmo nível, da mais
    populosa para a menos populosa). Use consultar_areas_risco(nivel="ALTO") para
    "Quais áreas possuem maior risco?".
    """
    areas = validar_lista(AreaRisco, await obter_backend().listar_areas_risco())
    resumo = contar_por([area.nivelRisco for area in areas])
    if nivel:
        areas = [area for area in areas if area.nivelRisco == nivel]

    areas.sort(key=lambda area: (-(gravidade(area.nivelRisco) or 0), -(area.populacaoEstimada or 0)))
    return resposta_lista(
        "areas",
        areas,
        filtros={"nivel": nivel},
        resumoPorNivel=resumo,
        populacaoEstimadaTotal=sum(area.populacaoEstimada or 0 for area in areas),
    )


FERRAMENTAS = [consultar_areas_risco]
