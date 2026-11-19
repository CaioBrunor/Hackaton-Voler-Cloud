# Centro de Comando Inteligente: Monitoramento de Enchentes e Defesa Civil

Projeto de Cidade Inteligente dividido em quatro partes, cada uma na sua pasta:

```text
┌──────────────────────────────┐
│   USUÁRIO (cidadão /         │
│   operador da Defesa Civil)  │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐        ┌──────────────────────────────┐
│  FRONTEND  (frontend/)       │        │  IA (Claude ou outra         │
│  TechZone, responsivo        │        │  compatível com MCP)         │
└──────┬───────────────┬───────┘        └──────────────┬───────────────┘
       │ REST          │ MCP (Inspetor)                │ MCP
       │               ↓                               ↓
       │        ┌──────────────────────────────────────────────┐
       │        │  MCP SERVER  (mcp-server/)                   │
       │        │  13 tools + 5 resources, somente leitura     │
       │        └──────────────────────┬───────────────────────┘
       │                               │ REST (só GET)
       ↓                               ↓
┌──────────────────────────────────────────────────────────────┐
│  BACKEND SPRING BOOT  (backend/)  ->  MySQL                  │
└──────────────────────────────────────────────────────────────┘
```

| Pasta | Parte | Tecnologia | Documentação |
|---|---|---|---|
| `backend/` | API REST: sensores, canais, bueiros, barragens, áreas de risco, alertas, ocorrências e previsão de chuva | Java 25, Spring Boot 4, MySQL | `backend/HELP.md` |
| `frontend/` | Telas do cidadão e da Defesa Civil (mapa, clima, abrigos, SOS) | HTML + Tailwind | — |
| `mcp-server/` | Ponte entre a IA e o backend: consultas e análise de risco por regras fixas | Python, SDK oficial do MCP | [`mcp-server/README.md`](mcp-server/README.md) |
| `assistente/` | IA do site: chat com painel de perguntas; o Claude responde usando as tools do MCP | Python, API do Claude (Sonnet 5.5) | [`assistente/README.md`](assistente/README.md) |

## Como rodar

### Demonstração rápida (sem MySQL)

Dois cliques em **`iniciar_demo.bat`**. Ele abre o backend **simulado** (imita o Spring Boot,
mesmas rotas e campos), o MCP Server e o frontend, e abre o navegador em
`http://127.0.0.1:5500`. Entre como **Defesa Civil**: o botão do topo mostra "MCP: Live".

### Projeto completo (backend real)

Requisitos: Java 25, MySQL rodando com o banco `centro_comando_defesa` e Python 3.10+.

1. Se o usuário `root` do MySQL tiver senha, defina antes (no mesmo terminal):
   `set SPRING_DATASOURCE_PASSWORD=sua_senha`
2. Rode **`iniciar_projeto.bat`**: backend Spring Boot (8080), MCP Server (8000) e frontend (5500).

Cada parte também pode ser iniciada sozinha:

| Arquivo | O que inicia | Porta |
|---|---|---|
| `iniciar_backend.bat` | Backend Spring Boot (`mvnw spring-boot:run`) | 8080 |
| `mcp-server\iniciar.bat` | MCP Server (cria o ambiente Python na 1ª vez) | 8000 |
| `mcp-server\simulador\iniciar_simulador.bat` | Backend simulado (no lugar do Spring Boot) | 8080 |
| `iniciar_assistente.bat` | Assistente de IA (pede a chave da API na 1ª vez) | 8100 |
| `iniciar_front.bat` | Frontend TechZone | 5500 |

> O backend real e o simulado usam a mesma porta (8080): rode só um dos dois.

### Assistente de IA no site

Clique em **IA** no cabeçalho do site: abre o chat com o painel de perguntas. Precisa da chave
da API da Anthropic em `assistente/.env` (veja [`assistente/README.md`](assistente/README.md)).

### Usar com o Claude Code / Claude Desktop

Com o backend (real ou simulado) rodando, o MCP pode ser usado no Claude Code ou no Claude
Desktop: veja a seção 9 do [README do MCP](mcp-server/README.md). Exemplo de pergunta:
*"Existe risco de enchente agora? Quais regiões precisam de mais atenção?"*

## Regras importantes

- O **MCP é somente leitura**: ele só faz GET no backend e nunca altera dados.
- O frontend continua usando o backend normalmente; a conexão com o MCP aparece no perfil
  Defesa Civil (análise de risco, clima e sensores reais, e o Inspetor MCP).
- Pedir SOS e despachar bombeiros são ações do frontend e **não passam pelo MCP**.
- As análises do MCP apoiam a decisão da Defesa Civil; não emitem ordens de evacuação.
