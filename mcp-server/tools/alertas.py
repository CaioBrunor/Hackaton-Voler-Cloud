"""Tool dos alertas."""

from typing import Annotated, Any

from pydantic import Field

from client.backend_client import obter_backend
from models.schemas import Alerta, contar_por, esta_ativo, resposta_lista, validar_lista


async def consultar_alertas(
    apenas_ativos: Annotated[
        bool,
        Field(description="true para só os alertas ativos (padrão); false para todos, inclusive encerrados."),
    ] = True,
) -> dict[str, Any]:
    """Lista os alertas com título, mensagem, severidade, local, horário e situação.

    Os alertas vêm do mais recente para o mais antigo, e resumoPorSeveridade traz a
    contagem por severidade. Use para "Quantos alertas estão ativos?".
    """
    alertas = validar_lista(Alerta, await obter_backend().listar_alertas())
    if apenas_ativos:
        # Ativo = qualquer situação que não seja de encerramento (ENCERRADO, RESOLVIDO...).
        alertas = [alerta for alerta in alertas if esta_ativo(alerta.situacao)]
    # Datas no formato ISO (padrão do Spring Boot) ordenam corretamente como texto.
    alertas.sort(key=lambda alerta: alerta.dataHora or "", reverse=True)
    return resposta_lista(
        "alertas",
        alertas,
        filtros={"apenas_ativos": apenas_ativos},
        resumoPorSeveridade=contar_por([alerta.severidade for alerta in alertas]),
    )


FERRAMENTAS = [consultar_alertas]
