"""Ponto de entrada do MCP Server do Centro de Comando de Monitoramento de Enchentes.

Cria o servidor MCP, registra as tools e os resources e inicia o transporte
escolhido no .env. Use o Python do ambiente virtual do projeto:

    iniciar.bat                           -> jeito mais fácil no Windows
    .venv\\Scripts\\python.exe main.py      -> HTTP em http://127.0.0.1:8000/mcp
"""

import logging
import sys

DEPENDENCIAS = {"mcp", "httpx", "pydantic", "dotenv", "starlette", "uvicorn", "anyio"}

try:
    from mcp.server.mcpserver import MCPServer
    import uvicorn
    from mcp.types import ToolAnnotations
    from starlette.applications import Starlette
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    import config
    from client.backend_client import BackendIndisponivel, obter_backend
    from models.schemas import ErroConsulta
    from resources import cidade
    from tools import alertas, areas_risco, barragens, bueiros, canais, chuva, ocorrencias, risco, sensores
    from utils.logs import configurar_logs, monitorar
except ModuleNotFoundError as exc:
    if (exc.name or "").split(".")[0] not in DEPENDENCIAS:
        raise
    # Acontece ao rodar com um Python que não tem as bibliotecas do projeto (ex.: o do sistema).
    sys.exit(
        f"Biblioteca não encontrada: {exc.name}\n"
        "Este Python não tem as dependências do projeto. Inicie o servidor com:\n"
        "    iniciar.bat\n"
        "ou com o Python do ambiente virtual:\n"
        "    .venv\\Scripts\\python.exe main.py\n"
        "(para instalar as dependências: .venv\\Scripts\\python.exe -m pip install -r requirements.txt)"
    )

logger = logging.getLogger("anti_enchente")

# Orientações enviadas à IA quando ela se conecta ao servidor.
INSTRUCOES = """\
Servidor MCP somente leitura do Centro de Comando de Monitoramento de Enchentes e Defesa Civil.
As ferramentas consultam a API do backend (Spring Boot) e fazem análises por regras fixas.

- Para uma visão geral, use consultar_situacao_cidade. Para combinar todas as fontes, use analisar_risco.
- Combine ferramentas quando a pergunta envolver mais de um tipo de dado
  (ex.: consultar_bueiros + consultar_areas_risco para bueiros obstruídos perto de áreas de risco).
- Se uma resposta trouxer o campo "erro", diga que a informação não está disponível. Nunca invente valores.
- Tendências descrevem leituras passadas: não as apresente como previsão certa.
- Não emita ordens de evacuação nem decisões operacionais: as análises apoiam a decisão
  dos responsáveis da Defesa Civil.
"""

# Nenhuma tool altera dados: todas são marcadas como somente leitura.
SOMENTE_LEITURA = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)

MODULOS_DE_TOOLS = (risco, chuva, sensores, canais, bueiros, barragens, areas_risco, alertas, ocorrencias)


async def pagina_de_status(request: Request) -> JSONResponse:
    """Resposta para quem abre o servidor no navegador: está rodando? o backend responde?"""
    try:
        await obter_backend().listar_sensores()  # qualquer rota de lista serve para testar a conexão
        backend = {"url": config.BACKEND_URL, "acessivel": True, "detalhe": "O backend respondeu."}
    except BackendIndisponivel as exc:
        backend = {"url": config.BACKEND_URL, "acessivel": False, "detalhe": f"{exc.erro} {exc.detalhe}"}
    except ErroConsulta as exc:
        # O backend respondeu, mas a rota do resumo falhou (ex.: 404).
        backend = {"url": config.BACKEND_URL, "acessivel": True, "detalhe": f"{exc.erro} {exc.detalhe}"}

    return JSONResponse(
        {
            "servidor": "anti-enchente",
            "status": "rodando",
            "mensagem": (
                "Este é um servidor MCP. Conecte um cliente MCP (MCP Inspector, Claude...) ao enderecoMcp; "
                "abrir esse endereço no navegador mostra erro 406, o que é normal."
            ),
            "enderecoMcp": f"{request.base_url}mcp",
            "tools": sum(len(modulo.FERRAMENTAS) for modulo in MODULOS_DE_TOOLS),
            "resources": len(cidade.RECURSOS),
            "backend": backend,
        }
    )


def criar_servidor() -> MCPServer:
    mcp = MCPServer(
        name="anti-enchente",
        title="Centro de Comando: Monitoramento de Enchentes",
        instructions=INSTRUCOES,
        version="1.0.0",
    )

    for modulo in MODULOS_DE_TOOLS:
        for ferramenta in modulo.FERRAMENTAS:
            mcp.add_tool(monitorar(ferramenta), annotations=SOMENTE_LEITURA)

    for recurso in cidade.RECURSOS:
        registrar = mcp.resource(
            recurso.uri, name=recurso.nome, description=recurso.descricao, mime_type="application/json"
        )
        registrar(monitorar(recurso.consulta, tipo="recurso"))

    mcp.custom_route("/", methods=["GET"])(pagina_de_status)
    return mcp


def criar_app_http(mcp: MCPServer) -> Starlette:
    """App HTTP do MCP com CORS, para o frontend (em outra porta) conseguir chamar pelo navegador."""
    app = mcp.streamable_http_app(host=config.MCP_HOST)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["content-type", "accept", "mcp-session-id", "mcp-protocol-version", "last-event-id"],
        expose_headers=["mcp-session-id"],
    )
    return app


def main() -> None:
    configurar_logs(config.LOG_LEVEL, config.LOG_FILE)
    mcp = criar_servidor()
    logger.info("Backend Spring Boot: %s (timeout de %gs)", config.BACKEND_URL, config.API_TIMEOUT)

    if config.MCP_TRANSPORT == "stdio":
        logger.info("MCP Server iniciado via stdio")
        mcp.run("stdio")
    else:
        logger.info("MCP Server iniciado em http://%s:%s/mcp", config.MCP_HOST, config.MCP_PORT)
        logger.info("Status no navegador: http://%s:%s/", config.MCP_HOST, config.MCP_PORT)
        logger.info("Frontend liberado (CORS): %s", ", ".join(config.CORS_ORIGINS))
        uvicorn.run(criar_app_http(mcp), host=config.MCP_HOST, port=config.MCP_PORT, log_level="warning")


if __name__ == "__main__":
    main()
