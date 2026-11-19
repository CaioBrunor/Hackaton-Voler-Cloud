"""Configuração do assistente, lida de variáveis de ambiente (ou do arquivo .env).

A chave da API da Anthropic (ANTHROPIC_API_KEY) também vem do ambiente, mas é lida
direto pelo SDK da Anthropic: nenhum outro arquivo a manipula, e ela nunca é enviada
ao navegador nem escrita em log.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega o .env da pasta do assistente. Variáveis já definidas no sistema têm prioridade.
load_dotenv(Path(__file__).resolve().parent / ".env")

ESFORCOS_VALIDOS = ("low", "medium", "high", "xhigh", "max")


def _texto(nome: str, padrao: str) -> str:
    return os.getenv(nome, "").strip() or padrao


def _inteiro(nome: str, padrao: int, minimo: int = 1) -> int:
    texto = _texto(nome, str(padrao))
    try:
        valor = int(texto)
    except ValueError:
        raise ValueError(f"{nome} deve ser um número inteiro (recebido: {texto!r}).") from None
    if valor < minimo:
        raise ValueError(f"{nome} deve ser pelo menos {minimo} (recebido: {valor}).")
    return valor


# --- Modelo ------------------------------------------------------------------------
# Claude Sonnet 5.5. Para trocar, defina ASSISTENTE_MODEL no .env.
MODELO = _texto("ASSISTENTE_MODEL", "claude-sonnet-5-5")

# Quanto o modelo "pensa" antes de responder. "medium" é o recomendado para uso com ferramentas.
ESFORCO = _texto("ASSISTENTE_EFFORT", "medium").lower()

# Tamanho máximo de cada resposta, em tokens.
MAX_TOKENS = _inteiro("ASSISTENTE_MAX_TOKENS", 16000, minimo=1024)

# Se a resposta for recusada por um filtro de segurança, a API tenta de novo em outro modelo.
# Desligue com ASSISTENTE_FALLBACK=0 se a sua conta não tiver acesso a esse recurso.
USAR_FALLBACK = _texto("ASSISTENTE_FALLBACK", "1") != "0"

# --- MCP Server --------------------------------------------------------------------
MCP_URL = _texto("MCP_URL", "http://127.0.0.1:8000/mcp")

# --- Servidor do assistente --------------------------------------------------------
HOST = _texto("ASSISTENTE_HOST", "127.0.0.1")
PORTA = _inteiro("ASSISTENTE_PORT", 8100)

# Endereços do frontend autorizados a usar o assistente (separados por vírgula).
CORS_ORIGINS = [
    origem.strip().rstrip("/")
    for origem in _texto("CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500").split(",")
    if origem.strip()
]

# --- Limites de uso (cada pergunta custa tokens da API) ----------------------------
LIMITE_PERGUNTA = _inteiro("ASSISTENTE_LIMITE_PERGUNTA", 2000)  # caracteres por pergunta
LIMITE_TURNOS = _inteiro("ASSISTENTE_LIMITE_TURNOS", 30)  # perguntas por conversa
LIMITE_SESSOES = _inteiro("ASSISTENTE_LIMITE_SESSOES", 200)  # conversas guardadas na memória
SESSAO_TTL = _inteiro("ASSISTENTE_SESSAO_TTL", 3600)  # segundos sem uso até esquecer a conversa
LIMITE_POR_MINUTO = _inteiro("ASSISTENTE_LIMITE_POR_MINUTO", 20)  # perguntas por minuto, por origem
MAX_CONCORRENCIA = _inteiro("ASSISTENTE_MAX_CONCORRENCIA", 4)  # conversas respondendo ao mesmo tempo
MAX_RODADAS = _inteiro("ASSISTENTE_MAX_RODADAS", 8)  # idas e vindas com as tools por pergunta
MAX_RESULTADO_TOOL = _inteiro("ASSISTENTE_MAX_RESULTADO_TOOL", 30000)  # caracteres de cada resultado

LOG_LEVEL = _texto("LOG_LEVEL", "INFO").upper()

if ESFORCO not in ESFORCOS_VALIDOS:
    raise ValueError(f"ASSISTENTE_EFFORT deve ser um de {ESFORCOS_VALIDOS} (recebido: {ESFORCO!r}).")
if not MCP_URL.startswith(("http://", "https://")):
    raise ValueError(f"MCP_URL deve começar com http:// ou https:// (recebido: {MCP_URL!r}).")


def chave_configurada() -> bool:
    """True se há credencial da Anthropic no ambiente (sem expor o valor)."""
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip())
