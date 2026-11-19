"""Logs de execução das tools e resources do MCP.

Cada chamada gera uma linha com ferramenta, horário, parâmetros, resultado e tempo:

    2026-11-19 15:42:07 | INFO | ferramenta=consultar_sensores | parametros={"status": "CRITICO"} | resultado=sucesso | tempo=48ms

Os logs vão para o stderr (no modo stdio o stdout é reservado ao protocolo MCP)
e, se LOG_FILE estiver definido, também para um arquivo. As respostas do backend
não são registradas, apenas os parâmetros recebidos.
"""

import functools
import json
import logging
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from models.schemas import ErroConsulta, resposta_erro

logger = logging.getLogger("anti_enchente")

_CHAVES_SENSIVEIS = ("senha", "password", "token", "secret", "segredo", "authorization", "cpf")
_TAMANHO_MAXIMO = 120


def configurar_logs(nivel: str = "INFO", arquivo: str = "") -> None:
    formato = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if arquivo:
        Path(arquivo).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(arquivo, encoding="utf-8"))

    logger.handlers.clear()
    for handler in handlers:
        handler.setFormatter(formato)
        logger.addHandler(handler)
    logger.setLevel(nivel)
    logger.propagate = False
    # A biblioteca httpx registra cada requisição em INFO; o MCP já registra o que importa.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _parametros_para_log(parametros: dict[str, Any]) -> str:
    """Parâmetros em JSON, com valores sensíveis mascarados e textos longos cortados."""
    seguros: dict[str, Any] = {}
    for nome, valor in parametros.items():
        if any(chave in nome.lower() for chave in _CHAVES_SENSIVEIS):
            seguros[nome] = "***"
        elif isinstance(valor, str) and len(valor) > _TAMANHO_MAXIMO:
            seguros[nome] = valor[:_TAMANHO_MAXIMO] + "..."
        else:
            seguros[nome] = valor
    return json.dumps(seguros, ensure_ascii=False, default=str)


def monitorar(
    funcao: Callable[..., Awaitable[dict[str, Any]]], tipo: str = "ferramenta"
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Envolve uma tool (ou resource) para registrar o log e padronizar os erros.

    * Falhas de consulta (backend fora do ar, registro inexistente, dados inválidos)
      viram {"erro": ..., "detalhe": ...} para a IA, sem dados inventados.
    * Erros inesperados também viram uma resposta de erro; o rastro completo fica
      só no log do servidor, sem expor detalhes internos à IA.
    """

    @functools.wraps(funcao)
    async def executar(*args: Any, **kwargs: Any) -> dict[str, Any]:
        inicio = time.perf_counter()
        try:
            resultado = await funcao(*args, **kwargs)
        except ErroConsulta as exc:
            resultado = resposta_erro(exc.erro, exc.detalhe)
        except Exception:
            logger.exception("%s=%s | erro inesperado", tipo, funcao.__name__)
            resultado = resposta_erro(
                "Erro interno no MCP ao executar a consulta.",
                "O erro foi registrado no log do servidor.",
            )

        tempo_ms = (time.perf_counter() - inicio) * 1000
        falhou = "erro" in resultado
        logger.log(
            logging.WARNING if falhou else logging.INFO,
            "%s=%s | parametros=%s | resultado=%s | tempo=%.0fms",
            tipo,
            funcao.__name__,
            _parametros_para_log(kwargs),
            f"erro ({resultado['erro']} {resultado['detalhe']})" if falhou else "sucesso",
            tempo_ms,
        )
        return resultado

    return executar
