"""Servidor do assistente: a página (frontend) conversa com ele, e ele conversa com o Claude.

    POST /chat    {"mensagem": "...", "sessaoId": "...", "perfil": "cidadao|defesa_civil"}
                  ->  resposta transmitida (SSE)
    GET  /        estado do assistente (chave configurada? MCP acessível?)

Segurança:
* a chave da API da Anthropic fica só aqui no servidor (no .env), nunca vai ao navegador;
* só os endereços de CORS_ORIGINS podem usar o assistente (sites de terceiros são recusados);
* limites de tamanho, de perguntas por minuto e de conversas simultâneas, porque cada pergunta
  gasta tokens pagos da API;
* o assistente só usa as tools de consulta do MCP: não altera nenhum dado.

Atenção: o perfil "Defesa Civil" do frontend ainda é só um botão de tela, sem login de verdade.
Quem alcançar este endereço pode usar o assistente. Por isso ele escuta só em 127.0.0.1 por padrão.
"""

import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from typing import Any

try:
    import uvicorn
    from mcp import Client
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, StreamingResponse
    from starlette.routing import Route

    import agente
    import config
    from sessoes import LimiteDeUso, Sessoes
except ModuleNotFoundError as exc:
    sys.exit(
        f"Biblioteca não encontrada: {exc.name}\n"
        "Inicie o assistente com iniciar_assistente.bat (na raiz do projeto)\n"
        "ou com o Python do ambiente virtual: assistente\\.venv\\Scripts\\python.exe main.py"
    )

logger = logging.getLogger("assistente")

sessoes = Sessoes()
limite_de_uso = LimiteDeUso()
vagas = asyncio.Semaphore(config.MAX_CONCORRENCIA)


def _erro(status: int, mensagem: str) -> JSONResponse:
    return JSONResponse({"erro": mensagem}, status_code=status)


def _sse(evento: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(evento, ensure_ascii=False)}\n\n".encode()


async def estado(request: Request) -> JSONResponse:
    """Para a página saber se o assistente está pronto, sem gastar nenhum token."""
    try:
        async with asyncio.timeout(3):
            async with Client(config.MCP_URL) as mcp:
                total_tools = len((await mcp.list_tools()).tools)
        mcp_estado = {"url": config.MCP_URL, "acessivel": True, "tools": total_tools}
    except Exception:
        mcp_estado = {"url": config.MCP_URL, "acessivel": False, "tools": 0}
    return JSONResponse(
        {
            "servico": "assistente",
            "modelo": config.MODELO,
            "chaveConfigurada": config.chave_configurada(),
            "mcp": mcp_estado,
        }
    )


async def chat(request: Request) -> StreamingResponse | JSONResponse:
    # Só o frontend autorizado pode usar o assistente (impede que outros sites gastem a sua chave).
    origem = request.headers.get("origin")
    if origem is not None and origem.rstrip("/") not in config.CORS_ORIGINS:
        logger.warning("pedido recusado: origem não autorizada (%s)", origem)
        return _erro(403, "Origem não autorizada.")

    if not config.chave_configurada():
        return _erro(503, "O assistente ainda não tem a chave da API. Configure ANTHROPIC_API_KEY no arquivo assistente/.env.")

    cliente = request.client.host if request.client else "desconhecido"
    if not limite_de_uso.permitir(cliente):
        return _erro(429, "Muitas perguntas em pouco tempo. Aguarde um instante.")

    try:
        corpo = await request.json()
    except ValueError:
        return _erro(400, "Corpo da requisição inválido.")
    mensagem = corpo.get("mensagem") if isinstance(corpo, dict) else None
    sessao_id = corpo.get("sessaoId") if isinstance(corpo, dict) else None
    perfil = corpo.get("perfil", "cidadao") if isinstance(corpo, dict) else None
    if not isinstance(mensagem, str) or not mensagem.strip():
        return _erro(400, "Escreva uma pergunta.")
    mensagem = mensagem.strip()
    if len(mensagem) > config.LIMITE_PERGUNTA:
        return _erro(413, f"A pergunta é longa demais (máximo de {config.LIMITE_PERGUNTA} caracteres).")
    if sessao_id is not None and not isinstance(sessao_id, str):
        return _erro(400, "Identificador de conversa inválido.")
    if perfil not in agente.PERFIS:
        return _erro(400, "Perfil inválido.")

    sessao = sessoes.obter_ou_criar(sessao_id, perfil)
    if sessao.turnos >= config.LIMITE_TURNOS:
        return _erro(409, "Esta conversa ficou longa. Comece uma nova conversa.")

    async def transmitir() -> AsyncIterator[bytes]:
        yield _sse({"type": "inicio", "sessaoId": sessao.id})
        async with vagas:
            async for evento in agente.conversar(sessao, mensagem):
                yield _sse(evento)

    return StreamingResponse(
        transmitir(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def criar_app() -> Starlette:
    return Starlette(
        routes=[Route("/", estado, methods=["GET"]), Route("/chat", chat, methods=["POST"])],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=config.CORS_ORIGINS,
                allow_methods=["GET", "POST"],
                allow_headers=["content-type"],
            )
        ],
    )


app = criar_app()


def main() -> None:
    logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    logger.info("Assistente com o modelo %s (esforço %s)", config.MODELO, config.ESFORCO)
    logger.info("MCP Server: %s", config.MCP_URL)
    if not config.chave_configurada():
        logger.warning("ANTHROPIC_API_KEY não configurada: defina no arquivo assistente/.env (veja .env.example)")
    logger.info("Assistente em http://%s:%s (frontend autorizado: %s)", config.HOST, config.PORTA, ", ".join(config.CORS_ORIGINS))
    uvicorn.run(app, host=config.HOST, port=config.PORTA, log_level="warning")


if __name__ == "__main__":
    main()
