"""Tool de previsão de chuva."""

from typing import Annotated, Any

from pydantic import Field

from client.backend_client import obter_backend
from models.schemas import PrevisaoChuva, contem, gravidade, ordenar_por_gravidade, resposta_lista, validar_lista


async def consultar_previsao_chuva(
    regiao: Annotated[
        str | None,
        Field(description="Nome da região ou bairro (ex.: 'Centro', 'Norte'). Omita para todas as regiões."),
    ] = None,
) -> dict[str, Any]:
    """Consulta a previsão de chuva por região: milímetros previstos, período e intensidade (FRACA, MODERADA, FORTE, MUITO_FORTE).

    O campo haPrevisaoChuvaForte indica se alguma previsão retornada é FORTE ou
    mais intensa. Use para perguntas como "Vai chover forte nas próximas horas?".
    """
    previsoes = validar_lista(PrevisaoChuva, await obter_backend().previsao_chuva())
    # Uma previsão sem região vale para a cidade toda, então entra em qualquer filtro.
    encontradas = [p for p in previsoes if p.regiao is None or contem(p.regiao, regiao)] if regiao else previsoes

    resposta = resposta_lista(
        "previsoes",
        ordenar_por_gravidade(encontradas, "intensidade"),
        filtros={"regiao": regiao},
        haPrevisaoChuvaForte=any((gravidade(p.intensidade) or 0) >= 2 for p in encontradas),
    )
    if regiao and not encontradas:
        resposta["mensagem"] = f"Nenhuma previsão encontrada para a região '{regiao}'."
        resposta["regioesDisponiveis"] = sorted({p.regiao for p in previsoes if p.regiao})
    return resposta


FERRAMENTAS = [consultar_previsao_chuva]
