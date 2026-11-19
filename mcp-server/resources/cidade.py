"""Resources do MCP: dados da cidade em JSON, somente leitura.

Tools são chamadas pela IA com parâmetros. Resources são documentos fixos, sem
parâmetros e identificados por uma URI, que o aplicativo de IA pode ler e anexar
como contexto. Cada resource reaproveita a consulta da tool equivalente, então
os dois devolvem sempre o mesmo formato.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from tools.alertas import consultar_alertas
from tools.areas_risco import consultar_areas_risco
from tools.barragens import consultar_barragens
from tools.risco import consultar_situacao_cidade
from tools.sensores import consultar_sensores


@dataclass(frozen=True)
class Recurso:
    uri: str
    nome: str
    descricao: str
    consulta: Callable[[], Awaitable[dict[str, Any]]]


async def situacao_atual() -> dict[str, Any]:
    return await consultar_situacao_cidade()


async def alertas_ativos() -> dict[str, Any]:
    return await consultar_alertas(apenas_ativos=True)


async def areas_risco() -> dict[str, Any]:
    return await consultar_areas_risco()


async def sensores() -> dict[str, Any]:
    return await consultar_sensores()


async def barragens() -> dict[str, Any]:
    return await consultar_barragens()


RECURSOS = [
    Recurso(
        "cidade://situacao-atual",
        "situacao-atual",
        "Resumo atual da cidade: situação geral, sensores e canais em alerta, alertas ativos e ocorrências abertas.",
        situacao_atual,
    ),
    Recurso("cidade://alertas-ativos", "alertas-ativos", "Alertas ativos, do mais recente para o mais antigo.", alertas_ativos),
    Recurso("cidade://areas-risco", "areas-risco", "Áreas de risco com população estimada e nível de risco.", areas_risco),
    Recurso("cidade://sensores", "sensores", "Todos os sensores de drenagem com nível, vazões e status.", sensores),
    Recurso("cidade://barragens", "barragens", "Todas as barragens com volume, percentual, vazões e status.", barragens),
]
