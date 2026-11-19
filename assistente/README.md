# Assistente de IA (Claude)

A camada de **IA** do projeto: um chat no site, com **painel de perguntas**, em que o Claude
responde dúvidas usando as tools do MCP Server.

```text
Site (frontend/js/assistente.js)
   │  POST /chat (resposta transmitida aos poucos)
   ▼
Assistente (esta pasta, porta 8100) ──► API do Claude (Claude Sonnet 5.5)
   │  chama as tools que o Claude pedir
   ▼
MCP Server (porta 8000) ──► Backend Spring Boot ──► MySQL
```

O MCP continua sem IA, como pede o enunciado. Quem conversa com o Claude é esta camada.

## Como usar

1. Crie uma chave em https://console.anthropic.com/settings/keys.
2. Dê dois cliques em **`iniciar_assistente.bat`** (na raiz do projeto). Na primeira vez ele
   instala tudo e abre o `.env` no Bloco de Notas: cole a chave em `ANTHROPIC_API_KEY=` e salve.
3. Com o MCP Server e o backend rodando, abra o site e clique no botão **IA** do cabeçalho.

`iniciar_projeto.bat` e `iniciar_demo.bat` já abrem o assistente junto com o resto.

## Painel de perguntas

Perguntas prontas, por assunto, diferentes para cada perfil:

| Perfil | Assuntos |
|---|---|
| Defesa Civil | Visão geral, Chuva, Sensores e canais, Bueiros e barragens, Áreas de risco, Ocorrências |
| Cidadão | Hoje na cidade, Perto de mim (com campo de bairro), O que fazer |

O usuário também pode escrever a pergunta. Cada resposta mostra quais consultas ao MCP foram
feitas (ex.: "✓ Análise de risco · 0,5 s"). O operador recebe respostas técnicas, e o cidadão recebe
linguagem simples, com os telefones 193 (Bombeiros) e 199 (Defesa Civil).

## Configuração (`assistente/.env`)

| Variável | Padrão | Para quê |
|---|---|---|
| `ANTHROPIC_API_KEY` | (obrigatória) | Chave da API. Fica só no servidor, nunca vai ao navegador nem ao Git. |
| `ASSISTENTE_MODEL` | `claude-sonnet-5-5` | Modelo do Claude. |
| `ASSISTENTE_EFFORT` | `medium` | Quanto o modelo raciocina (`low` a `max`). |
| `MCP_URL` | `http://127.0.0.1:8000/mcp` | Endereço do MCP Server. |
| `ASSISTENTE_PORT` | `8100` | Porta do assistente. |
| `CORS_ORIGINS` | `http://127.0.0.1:5500,...` | Sites autorizados a usar o assistente. |
| `ASSISTENTE_LIMITE_POR_MINUTO` | `20` | Perguntas por minuto aceitas de cada origem. |
| `ASSISTENTE_FALLBACK` | `1` | Se a resposta for recusada por um filtro de segurança, a API tenta em outro modelo. `0` desliga. |

## Segurança e custo

- **Somente leitura:** o Claude só tem as tools de consulta do MCP; não altera nenhum dado.
- **Chave protegida:** fica no `.env` do servidor; o site nunca a recebe.
- **Só o seu site:** pedidos de outras origens são recusados (protege a sua chave de uso por terceiros).
- **Limites:** tamanho da pergunta, perguntas por minuto, conversas simultâneas e consultas por
  pergunta. Cada pergunta gasta tokens pagos da API (no Sonnet 5.5, US$ 2 por milhão de tokens de
  entrada e US$ 10 de saída; uma pergunta típica com consultas ao MCP custa poucos centavos).
- **Sem login de verdade:** o perfil Defesa Civil do site ainda é só um botão. Por isso o assistente
  escuta apenas em `127.0.0.1`. Para publicar na internet, é preciso autenticação antes.
- **Dados como dados:** textos cadastrados no backend (alertas, ocorrências) são tratados como
  informação, nunca como instrução para a IA.

## Testes

```powershell
assistente\.venv\Scripts\python.exe -m pytest      # dentro da pasta assistente
```

Os testes não gastam tokens: usam um Claude simulado e também o SDK real da Anthropic contra um
servidor de mentira que fala o protocolo de streaming da API.
