"""Tool das ocorrências da Defesa Civil."""

from typing import Annotated, Any

from pydantic import Field

from client.backend_client import obter_backend
from models.schemas import Ocorrencia, contar_por, esta_ativo, gravidade, normalizar, resposta_lista, validar_lista


async def consultar_ocorrencias(
    status: Annotated[
        str,
        Field(description="Status das ocorrências, ex.: ABERTA (padrão), EM_ATENDIMENTO, ENCERRADA, ou TODAS."),
    ] = "ABERTA",
) -> dict[str, Any]:
    """Lista as ocorrências da Defesa Civil com localização, descrição, prioridade, tipo, horário e status.

    Por padrão traz só as ocorrências abertas (as que ainda não foram encerradas). As mais prioritárias vêm primeiro
    (e, na mesma prioridade, as mais recentes).
    """
    filtro = normalizar(status)
    ocorrencias = validar_lista(Ocorrencia, await obter_backend().listar_ocorrencias())
    if filtro in ("ABERTA", "ABERTAS"):
        # Aberta = ainda não encerrada (inclui as que estão em atendimento).
        ocorrencias = [ocorrencia for ocorrencia in ocorrencias if esta_ativo(ocorrencia.status)]
    elif filtro != "TODAS":
        ocorrencias = [ocorrencia for ocorrencia in ocorrencias if ocorrencia.status == filtro]

    # Duas ordenações estáveis: primeiro por horário, depois por prioridade.
    ocorrencias.sort(key=lambda ocorrencia: ocorrencia.dataHora or "", reverse=True)
    ocorrencias.sort(key=lambda ocorrencia: -(gravidade(ocorrencia.prioridade) or 0))
    return resposta_lista(
        "ocorrencias",
        ocorrencias,
        filtros={"status": filtro},
        resumoPorPrioridade=contar_por([ocorrencia.prioridade for ocorrencia in ocorrencias]),
    )


FERRAMENTAS = [consultar_ocorrencias]
