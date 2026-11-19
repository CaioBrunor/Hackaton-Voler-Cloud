"""Configuração do MCP Server, lida de variáveis de ambiente (ou do arquivo .env).

URLs, portas e tempos limite ficam todos aqui: nenhum outro arquivo lê
variáveis de ambiente ou tem endereços escritos diretamente no código.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega o .env da pasta do projeto, se existir.
# Variáveis já definidas no sistema têm prioridade sobre o arquivo.
load_dotenv(Path(__file__).resolve().parent / ".env")

TRANSPORTES_VALIDOS = ("streamable-http", "stdio")
NIVEIS_DE_LOG_VALIDOS = ("DEBUG", "INFO", "WARNING", "ERROR")


def _ler_texto(nome: str, padrao: str) -> str:
    valor = os.getenv(nome, "").strip()
    return valor or padrao


def _ler_inteiro(nome: str, padrao: int) -> int:
    texto = _ler_texto(nome, str(padrao))
    try:
        return int(texto)
    except ValueError:
        raise ValueError(f"{nome} deve ser um número inteiro (recebido: {texto!r}).") from None


def _ler_decimal(nome: str, padrao: float) -> float:
    texto = _ler_texto(nome, str(padrao))
    try:
        return float(texto)
    except ValueError:
        raise ValueError(f"{nome} deve ser um número (recebido: {texto!r}).") from None


# Endereço da API REST do backend Spring Boot.
BACKEND_URL = _ler_texto("BACKEND_URL", "http://localhost:8080").rstrip("/")

# Endereço em que o próprio MCP Server escuta (transporte HTTP).
MCP_HOST = _ler_texto("MCP_HOST", "127.0.0.1")
MCP_PORT = _ler_inteiro("MCP_PORT", 8000)

# Tempo máximo, em segundos, de espera por uma resposta do backend.
API_TIMEOUT = _ler_decimal("API_TIMEOUT", 10.0)

# "streamable-http" (servidor HTTP) ou "stdio" (aplicativo de IA inicia o processo).
MCP_TRANSPORT = _ler_texto("MCP_TRANSPORT", "streamable-http").lower()

# Endereços do frontend que podem chamar o MCP pelo navegador (CORS), separados por vírgula.
CORS_ORIGINS = [
    origem.strip().rstrip("/")
    for origem in _ler_texto("CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500").split(",")
    if origem.strip()
]

LOG_LEVEL = _ler_texto("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "").strip()


if not BACKEND_URL.startswith(("http://", "https://")):
    raise ValueError(f"BACKEND_URL deve começar com http:// ou https:// (recebido: {BACKEND_URL!r}).")
if not 1 <= MCP_PORT <= 65535:
    raise ValueError(f"MCP_PORT deve estar entre 1 e 65535 (recebido: {MCP_PORT}).")
if API_TIMEOUT <= 0:
    raise ValueError(f"API_TIMEOUT deve ser maior que zero (recebido: {API_TIMEOUT}).")
if MCP_TRANSPORT not in TRANSPORTES_VALIDOS:
    raise ValueError(f"MCP_TRANSPORT deve ser um de {TRANSPORTES_VALIDOS} (recebido: {MCP_TRANSPORT!r}).")
if LOG_LEVEL not in NIVEIS_DE_LOG_VALIDOS:
    raise ValueError(f"LOG_LEVEL deve ser um de {NIVEIS_DE_LOG_VALIDOS} (recebido: {LOG_LEVEL!r}).")
