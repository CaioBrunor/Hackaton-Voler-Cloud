"""Tools dos canais de drenagem: lista com filtros e análise de fluxo."""

from typing import Annotated, Any

from pydantic import Field

from client.backend_client import RecursoNaoEncontrado, obter_backend
from models.schemas import (
    Canal,
    StatusMonitoramento,
    contar_por,
    ordenar_por_percentual,
    resposta_erro,
    resposta_lista,
    validar,
    validar_lista,
)
from services.analise_risco import analisar_fluxo


async def consultar_canais(
    status: Annotated[
        StatusMonitoramento | None,
        Field(description="Filtra pela situação do canal. Omita para listar todos."),
    ] = None,
    percentual_minimo: Annotated[
        float | None,
        Field(ge=0, le=100, description="Só canais com ocupação maior ou igual a este percentual (ex.: 80)."),
    ] = None,
) -> dict[str, Any]:
    """Lista os canais de drenagem com nível, percentual de ocupação, vazões de entrada/saída e situação.

    Filtros opcionais: status (NORMAL, ATENCAO, ALERTA, CRITICO) e percentual_minimo,
    por exemplo consultar_canais(percentual_minimo=80) para "Quais canais estão acima
    de 80%?". Os canais vêm do mais cheio para o mais vazio. saldoVazao é entrada
    menos saída, e canaisComEntradaMaiorQueSaida lista os canais com saldo positivo.
    """
    canais = validar_lista(Canal, await obter_backend().listar_canais())
    resumo = contar_por([canal.status for canal in canais])
    if status:
        canais = [canal for canal in canais if canal.status == status]
    if percentual_minimo is not None:
        canais = [c for c in canais if c.percentual is not None and c.percentual >= percentual_minimo]

    canais = ordenar_por_percentual(canais)
    return resposta_lista(
        "canais",
        canais,
        filtros={"status": status, "percentual_minimo": percentual_minimo},
        resumoPorStatus=resumo,
        canaisComEntradaMaiorQueSaida=[c.nome or c.id for c in canais if (c.saldoVazao or 0) > 0],
    )


async def analisar_fluxo_canal(
    id: Annotated[int, Field(ge=1, description="Id numérico do canal (veja consultar_canais).")],
) -> dict[str, Any]:
    """Compara a vazão de entrada com a de saída de um canal e calcula o saldo (entrada - saída).

    Saldo positivo indica acúmulo potencial de água. É um indicador descritivo:
    sozinho, não permite afirmar que haverá enchente.
    """
    try:
        dados = await obter_backend().obter_canal(id)
    except RecursoNaoEncontrado:
        return resposta_erro(f"Canal {id} não encontrado.", "Confira o id com a ferramenta consultar_canais.")

    canal = validar(Canal, dados)
    campos = {"id", "nome", "localizacao", "regiao", "percentual", "status", "ultimaAtualizacao"}
    return {
        "canal": canal.model_dump(include=campos),
        "fluxo": analisar_fluxo(canal.vazaoEntrada, canal.vazaoSaida).model_dump(),
    }


FERRAMENTAS = [consultar_canais, analisar_fluxo_canal]
