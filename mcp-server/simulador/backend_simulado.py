"""Backend simulado: substitui o Spring Boot (pasta backend/) APENAS para demonstração.

Imita o backend real da equipe: as mesmas rotas GET (/api/sensores, /api/canais,
/api/previsoes-chuva...) e os mesmos campos das entidades Java (local, nivelAgua,
entradaAgua, saidaAgua, quantidadeChuva...). Assim o MCP é testado do mesmo jeito que
será usado com o Spring Boot. Use quando o backend real (Java + MySQL) não estiver no ar.

    .venv\\Scripts\\python.exe simulador\\backend_simulado.py    -> http://127.0.0.1:8080

Os horários são gerados a cada requisição, então os dados parecem sempre atuais.
"""

import os
from datetime import datetime, timedelta

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

PORTA = int(os.getenv("SIMULADOR_PORT", "8080"))


def _horario(minutos_atras: int) -> str:
    """Data no formato do LocalDateTime do Spring Boot (ISO, sem fuso)."""
    return (datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=minutos_atras)).isoformat()


# ---------------------------------------------------------------- dados (formato das entidades Java)


def previsoes() -> list[dict]:
    return [
        {"id": 1, "local": "Centro", "dataHora": _horario(-180), "quantidadeChuva": 80.0, "intensidade": "FORTE"},
        {"id": 2, "local": "Norte", "dataHora": _horario(-180), "quantidadeChuva": 45.0, "intensidade": "MODERADA"},
        {"id": 3, "local": "Leste", "dataHora": _horario(-180), "quantidadeChuva": 20.0, "intensidade": "MODERADA"},
        {"id": 4, "local": "Sul", "dataHora": _horario(-180), "quantidadeChuva": 8.0, "intensidade": "FRACA"},
        {"id": 5, "local": "Oeste", "dataHora": _horario(-180), "quantidadeChuva": 5.0, "intensidade": "FRACA"},
    ]


SENSORES = [  # SensorDrenagem: nome, local, nivelAgua (m), status
    {"id": 1, "nome": "DRN-001 Av. Beira Rio", "local": "Norte", "nivelAgua": 3.28, "status": "ALERTA"},
    {"id": 2, "nome": "DRN-002 Rua das Flores", "local": "Centro", "nivelAgua": 1.80, "status": "NORMAL"},
    {"id": 3, "nome": "DRN-003 Praça Central", "local": "Centro", "nivelAgua": 3.72, "status": "CRITICO"},
    {"id": 4, "nome": "DRN-004 Av. Atlântica", "local": "Sul", "nivelAgua": 1.52, "status": "NORMAL"},
    {"id": 5, "nome": "DRN-005 Rua do Porto", "local": "Leste", "nivelAgua": 2.96, "status": "ATENCAO"},
    {"id": 6, "nome": "DRN-006 Av. das Palmeiras", "local": "Oeste", "nivelAgua": 2.08, "status": "NORMAL"},
    {"id": 7, "nome": "DRN-007 Travessa do Mercado", "local": "Centro", "nivelAgua": 3.16, "status": "ATENCAO"},
]

CANAIS = [  # Canal: nome, local, nivelAgua, capacidade, entradaAgua, saidaAgua (m³/h), status
    {"id": 1, "nome": "Canal Centro", "local": "Centro", "nivelAgua": 2.28, "capacidade": 3.0,
     "entradaAgua": 650.0, "saidaAgua": 600.0, "status": "ATENCAO"},
    {"id": 2, "nome": "Canal Sul", "local": "Sul", "nivelAgua": 1.23, "capacidade": 3.0,
     "entradaAgua": 400.0, "saidaAgua": 450.0, "status": "NORMAL"},
    {"id": 3, "nome": "Canal Norte", "local": "Norte", "nivelAgua": 2.61, "capacidade": 3.0,
     "entradaAgua": 920.0, "saidaAgua": 640.0, "status": "ALERTA"},
    {"id": 4, "nome": "Canal Leste", "local": "Leste", "nivelAgua": 2.04, "capacidade": 3.0,
     "entradaAgua": 380.0, "saidaAgua": 390.0, "status": "NORMAL"},
]  # fmt: skip

BUEIROS = [  # Bueiro: local, status, nivelObstrucao (%), ultimaManutencao
    {"id": 1, "local": "Av. Beira Rio, 180 - Norte", "status": "OBSTRUIDO", "nivelObstrucao": 90.0, "ultimaManutencao": "2026-08-10"},
    {"id": 2, "local": "Rua das Flores, 40 - Centro", "status": "PARCIALMENTE_OBSTRUIDO", "nivelObstrucao": 45.0, "ultimaManutencao": "2026-09-02"},
    {"id": 3, "local": "Av. Atlântica, 950 - Sul", "status": "NORMAL", "nivelObstrucao": 5.0, "ultimaManutencao": "2026-10-20"},
    {"id": 4, "local": "Rua do Porto, 30 - Leste", "status": "NORMAL", "nivelObstrucao": 10.0, "ultimaManutencao": "2026-10-01"},
    {"id": 5, "local": "Praça Central - Centro", "status": "OBSTRUIDO", "nivelObstrucao": 85.0, "ultimaManutencao": "2026-07-15"},
]

BARRAGENS = [  # Barragem: nome, local, nivelAgua, capacidade, volumeAtual, nivelRisco, status
    {"id": 1, "nome": "Barragem Serra Azul", "local": "Oeste", "nivelAgua": 43.0, "capacidade": 1_000_000.0,
     "volumeAtual": 860_000.0, "nivelRisco": "ALTO", "status": "ALERTA"},
    {"id": 2, "nome": "Barragem Rio Claro", "local": "Norte", "nivelAgua": 21.5, "capacidade": 500_000.0,
     "volumeAtual": 260_000.0, "nivelRisco": "BAIXO", "status": "NORMAL"},
]  # fmt: skip

AREAS_RISCO = [  # AreaRisco: nome, local, tipoRisco, nivelRisco, descricao, status
    {"id": 1, "nome": "Norte", "local": "Vila Esperança", "tipoRisco": "ALAGAMENTO", "nivelRisco": "ALTO",
     "descricao": "Casas próximas ao Canal Norte", "status": "EM_MONITORAMENTO"},
    {"id": 2, "nome": "Centro", "local": "Praça Central", "tipoRisco": "ALAGAMENTO", "nivelRisco": "CRITICO",
     "descricao": "Área baixa com histórico de alagamento", "status": "EM_MONITORAMENTO"},
    {"id": 3, "nome": "Leste", "local": "Morro do Sol", "tipoRisco": "DESLIZAMENTO", "nivelRisco": "MEDIO",
     "descricao": "Encosta com solo encharcado", "status": "NORMAL"},
    {"id": 4, "nome": "Sul", "local": "Orla", "tipoRisco": "ALAGAMENTO", "nivelRisco": "BAIXO",
     "descricao": "Escoamento rápido para o mar", "status": "NORMAL"},
]  # fmt: skip


def alertas() -> list[dict]:  # Alerta: titulo, descricao, nivel, local, dataHora, status
    return [
        {"id": 1, "titulo": "Nível crítico", "descricao": "Sensor DRN-003 na Praça Central acima de 90%",
         "nivel": "CRITICO", "local": "Centro", "dataHora": _horario(10), "status": "ATIVO"},
        {"id": 2, "titulo": "Canal em alerta", "descricao": "Canal Norte acima de 85% da capacidade",
         "nivel": "ALTO", "local": "Norte", "dataHora": _horario(25), "status": "ATIVO"},
        {"id": 3, "titulo": "Chuva forte", "descricao": "Previsão de 80 mm nas próximas 3 horas",
         "nivel": "ALTO", "local": "Centro", "dataHora": _horario(40), "status": "ATIVO"},
        {"id": 4, "titulo": "Bueiro obstruído", "descricao": "Bueiro na Av. Beira Rio obstruído",
         "nivel": "MEDIO", "local": "Norte", "dataHora": _horario(60), "status": "ATIVO"},
        {"id": 5, "titulo": "Canal em alerta", "descricao": "Canal Sul acima de 80% da capacidade",
         "nivel": "ALTO", "local": "Sul", "dataHora": _horario(26 * 60), "status": "ENCERRADO"},
    ]  # fmt: skip


def ocorrencias() -> list[dict]:  # Ocorrencia: tipo, descricao, local, nivel, dataHora, status
    return [
        {"id": 1, "tipo": "ALAGAMENTO", "descricao": "Rua alagada, carros com dificuldade de passagem",
         "local": "Rua das Flores, 45 - Centro", "nivel": "ALTO", "dataHora": _horario(30), "status": "ABERTA"},
        {"id": 2, "tipo": "DESLIZAMENTO", "descricao": "Queda de barreira em encosta",
         "local": "Morro do Sol - Leste", "nivel": "ALTO", "dataHora": _horario(70), "status": "ABERTA"},
        {"id": 3, "tipo": "ARVORE_CAIDA", "descricao": "Árvore sobre a via",
         "local": "Av. Atlântica, 700 - Sul", "nivel": "MEDIO", "dataHora": _horario(180), "status": "EM_ATENDIMENTO"},
        {"id": 4, "tipo": "ALAGAMENTO", "descricao": "Água acumulada após a chuva",
         "local": "Rua do Porto, 80 - Leste", "nivel": "BAIXO", "dataHora": _horario(28 * 60), "status": "ENCERRADA"},
    ]  # fmt: skip


# ---------------------------------------------------------------- rotas (as mesmas GET do Spring Boot)


def _lista(dados):
    async def responder(request: Request) -> JSONResponse:
        return JSONResponse(dados() if callable(dados) else dados)

    return responder


ROTAS = [
    Route("/api/previsoes-chuva", _lista(previsoes), methods=["GET"]),
    Route("/api/sensores", _lista(SENSORES), methods=["GET"]),
    Route("/api/canais", _lista(CANAIS), methods=["GET"]),
    Route("/api/bueiros", _lista(BUEIROS), methods=["GET"]),
    Route("/api/barragens", _lista(BARRAGENS), methods=["GET"]),
    Route("/api/areas-risco", _lista(AREAS_RISCO), methods=["GET"]),
    Route("/api/alertas", _lista(alertas), methods=["GET"]),
    Route("/api/ocorrencias", _lista(ocorrencias), methods=["GET"]),
]

app = Starlette(routes=ROTAS)


if __name__ == "__main__":
    import uvicorn

    print(f"Backend simulado rodando em http://127.0.0.1:{PORTA}  (Ctrl+C para encerrar)")
    print("Imita o Spring Boot da pasta backend/; feche-o quando o backend real estiver no ar.")
    uvicorn.run(app, host="127.0.0.1", port=PORTA, log_level="warning")
