"""Respostas simuladas do backend Spring Boot, usadas só nos testes.

Alguns registros usam de propósito nomes alternativos de campo ("entrada",
"situacao", "nome", "populacao") e valores com acento ("Crítico") para
garantir que o MCP normaliza o que recebe.
"""

RESUMO = {
    "situacaoGeral": "ALERTA",
    "sensoresAtivos": 24,
    "sensoresEmAlerta": 3,
    "canaisEmAlerta": 2,
    "barragensEmAlerta": 1,
    "alertasAtivos": 4,
    "ocorrenciasAbertas": 2,
}

PREVISOES = [
    {"regiao": "Centro", "chuvaPrevista": 80, "periodo": "3 horas", "intensidade": "FORTE"},
    {"regiao": "Norte", "chuvaPrevista": 35, "periodo": "3 horas", "intensidade": "MODERADA"},
    {"regiao": "Sul", "chuvaPrevista": 5, "periodo": "3 horas", "intensidade": "FRACA"},
]

SENSORES = [
    {
        "id": 1, "codigo": "DRN-001", "localizacao": "Av. Beira Rio", "regiao": "Norte",
        "nivel": 3.28, "capacidade": 4.0, "percentual": 82, "vazaoEntrada": 920, "vazaoSaida": 640,
        "status": "ALERTA", "ultimaAtualizacao": "2026-11-19T15:30:00",
    },
    {
        "id": 2, "codigo": "DRN-002", "localizacao": "Rua das Flores", "regiao": "Centro",
        "nivel": 1.6, "capacidade": 4.0, "percentual": 40, "vazaoEntrada": 300, "vazaoSaida": 310,
        "status": "NORMAL", "ultimaAtualizacao": "2026-11-19T15:30:00",
    },
    {
        "id": 3, "codigo": "DRN-003", "localizacao": "Praça Central", "regiao": "Centro",
        "nivel": 3.72, "capacidade": 4.0, "percentual": 93, "vazaoEntrada": 700, "vazaoSaida": 500,
        "status": "Crítico", "ultimaAtualizacao": "2026-11-19T15:29:00",
    },
    # Sensor sem leitura atual.
    {"id": 4, "codigo": "DRN-004", "localizacao": "Av. Sul", "regiao": "Sul", "capacidade": 4.0, "status": "NORMAL"},
]  # fmt: skip

# Histórico do sensor 1 fora de ordem, para conferir a ordenação por horário.
HISTORICO_SENSOR_1 = [
    {"dataHora": "2026-11-19T15:00:00", "nivel": 3.24, "percentual": 81},
    {"dataHora": "2026-11-19T12:00:00", "nivel": 1.60, "percentual": 40},
    {"dataHora": "2026-11-19T14:00:00", "nivel": 2.68, "percentual": 67},
    {"dataHora": "2026-11-19T13:00:00", "nivel": 2.08, "percentual": 52},
]

CANAIS = [
    {
        "id": 3, "nome": "Canal Norte", "localizacao": "Bairro Norte", "regiao": "Norte",
        "nivel": 2.61, "capacidade": 3.0, "percentual": 87, "entrada": 920, "saida": 640, "situacao": "ALERTA",
    },
    {
        "id": 4, "nome": "Canal Sul", "localizacao": "Bairro Sul", "regiao": "Sul",
        "percentual": 45, "vazaoEntrada": 400, "vazaoSaida": 450, "status": "NORMAL",
    },
]  # fmt: skip

BUEIROS = [
    {"id": 1, "codigo": "BU-101", "localizacao": "Rua A", "regiao": "Norte", "status": "OBSTRUIDO"},
    {"id": 2, "codigo": "BU-102", "localizacao": "Rua B", "regiao": "Centro", "status": "parcialmente obstruído"},
    {"id": 3, "codigo": "BU-103", "localizacao": "Rua C", "regiao": "Sul", "status": "NORMAL"},
]

BARRAGENS = [
    # Sem "percentual": o MCP calcula a partir do volume (910.000 / 1.000.000 = 91%).
    {
        "id": 1, "nome": "Barragem Serra Azul", "localizacao": "Serra Azul", "regiao": "Oeste",
        "capacidade": 1_000_000, "volumeAtual": 910_000, "vazaoEntrada": 1500, "vazaoSaida": 1200,
        "nivel": 45.5, "status": "ALERTA",
    },
    {
        "id": 2, "nome": "Barragem Rio Claro", "localizacao": "Rio Claro",
        "capacidade": 500_000, "volumeAtual": 250_000, "percentual": 50, "status": "NORMAL",
    },
]  # fmt: skip

AREAS_RISCO = [
    {"id": 1, "regiao": "Região Norte", "populacaoEstimada": 12000, "nivelRisco": "ALTO", "situacaoAtual": "Em monitoramento"},
    {"id": 2, "nome": "Centro", "populacao": 8000, "nivel": "CRITICO", "situacao": "Em monitoramento"},
    {"id": 3, "regiao": "Sul", "populacaoEstimada": 3000, "nivelRisco": "BAIXO", "situacaoAtual": "Normal"},
]

ALERTAS_ATIVOS = [
    {
        "id": 1, "tipo": "NIVEL_ALTO", "mensagem": "Canal Norte acima de 85%", "severidade": "ALTA",
        "regiao": "Norte", "dataHora": "2026-11-19T15:00:00", "situacao": "ATIVO",
    },
    {
        "id": 2, "tipo": "CHUVA_FORTE", "mensagem": "Previsão de chuva forte", "severidade": "MEDIA",
        "regiao": "Centro", "dataHora": "2026-11-19T15:20:00", "situacao": "ATIVO",
    },
]  # fmt: skip

ALERTAS_TODOS = [
    *ALERTAS_ATIVOS,
    {
        "id": 3, "tipo": "NIVEL_ALTO", "mensagem": "Canal Sul acima de 80%", "severidade": "ALTA",
        "regiao": "Sul", "dataHora": "2026-11-18T10:00:00", "situacao": "ENCERRADO",
    },
]  # fmt: skip

OCORRENCIAS_ABERTAS = [
    {
        "id": 1, "tipo": "ALAGAMENTO", "descricao": "Rua alagada", "localizacao": "Rua A",
        "prioridade": "MEDIA", "dataHora": "2026-11-19T14:00:00", "status": "ABERTA",
    },
    {
        "id": 2, "tipo": "DESLIZAMENTO", "descricao": "Queda de barreira", "localizacao": "Morro do Sol",
        "prioridade": "ALTA", "dataHora": "2026-11-19T13:00:00", "status": "ABERTA",
    },
]  # fmt: skip

OCORRENCIAS_TODAS = [
    *OCORRENCIAS_ABERTAS,
    {
        "id": 3, "tipo": "ALAGAMENTO", "descricao": "Água acumulada", "localizacao": "Rua C",
        "prioridade": "BAIXA", "dataHora": "2026-11-18T09:00:00", "status": "ENCERRADA",
    },
    {
        "id": 4, "tipo": "ARVORE_CAIDA", "descricao": "Árvore sobre a via", "localizacao": "Rua D",
        "prioridade": "MEDIA", "dataHora": "2026-11-19T11:00:00", "status": "EM_ATENDIMENTO",
    },
]  # fmt: skip

# Caminho da API -> corpo da resposta (rotas do Spring Boot + as duas opcionais).
ROTAS = {
    "/api/dashboard/resumo": RESUMO,  # opcional: o backend real ainda não tem
    "/api/previsoes-chuva": PREVISOES,
    "/api/sensores": SENSORES,
    "/api/sensores/1/historico": HISTORICO_SENSOR_1,  # opcional: o backend real ainda não tem
    "/api/canais": CANAIS,
    "/api/bueiros": BUEIROS,
    "/api/barragens": BARRAGENS,
    "/api/areas-risco": AREAS_RISCO,
    "/api/alertas": ALERTAS_TODOS,
    "/api/ocorrencias": OCORRENCIAS_TODAS,
}
