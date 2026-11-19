"""O frontend (servido em outra porta) consegue usar o MCP pelo navegador."""

from starlette.testclient import TestClient

from main import criar_app_http, criar_servidor

ORIGEM_FRONT = "http://127.0.0.1:5500"
CABECALHOS = {"Origin": ORIGEM_FRONT, "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _rpc(id_, metodo, params=None):
    corpo = {"jsonrpc": "2.0", "method": metodo, "params": params or {}}
    if id_ is not None:
        corpo["id"] = id_
    return corpo


def test_preflight_cors_libera_o_frontend():
    with TestClient(criar_app_http(criar_servidor()), base_url="http://127.0.0.1:8000") as http:
        resposta = http.options(
            "/mcp",
            headers={
                "Origin": ORIGEM_FRONT,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,mcp-session-id,mcp-protocol-version",
            },
        )
    assert resposta.status_code == 200
    assert resposta.headers["access-control-allow-origin"] == ORIGEM_FRONT


def test_origem_desconhecida_nao_recebe_cors():
    with TestClient(criar_app_http(criar_servidor()), base_url="http://127.0.0.1:8000") as http:
        resposta = http.options(
            "/mcp", headers={"Origin": "http://site-qualquer.com", "Access-Control-Request-Method": "POST"}
        )
    assert "access-control-allow-origin" not in resposta.headers


def test_handshake_e_chamada_de_tool_como_o_navegador_faz(backend):
    with TestClient(criar_app_http(criar_servidor()), base_url="http://127.0.0.1:8000") as http:
        inicio = http.post(
            "/mcp",
            headers=CABECALHOS,
            json=_rpc(1, "initialize", {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "techzone-front", "version": "1.0"},
            }),
        )
        assert inicio.status_code == 200
        assert inicio.headers["access-control-allow-origin"] == ORIGEM_FRONT
        assert "mcp-session-id" in inicio.headers["access-control-expose-headers"].lower()
        sessao = {**CABECALHOS, "mcp-session-id": inicio.headers["mcp-session-id"], "mcp-protocol-version": "2025-11-25"}

        assert http.post("/mcp", headers=sessao, json=_rpc(None, "notifications/initialized")).status_code == 202
        chamada = http.post("/mcp", headers=sessao, json=_rpc(2, "tools/call", {"name": "consultar_sensores", "arguments": {}}))
    assert chamada.status_code == 200
    assert '"total"' in chamada.text and "DRN-003" in chamada.text
