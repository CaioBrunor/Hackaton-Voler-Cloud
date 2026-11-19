# MCP Server: Centro de Comando de Monitoramento de Enchentes

Servidor **MCP (Model Context Protocol)** que permite a uma IA consultar os dados do
**Centro de Comando Inteligente para Monitoramento de Enchentes e Defesa Civil**,
analisar a situação da cidade e apoiar os operadores da Defesa Civil.

O MCP é uma camada separada: ele **não substitui o backend Spring Boot**, **não acessa o
banco de dados** e **não altera nenhum dado**. Ele só consulta a API REST do backend e
faz análises com regras fixas.

## Arquitetura

```text
              ┌─────────────┐
              │     IA      │
              └──────┬──────┘
                     │
                    MCP
                     │
              ┌──────▼──────┐
              │ MCP SERVER  │
              └──────┬──────┘
                     │
                  REST API
                     │
              ┌──────▼──────┐
              │ SPRING BOOT │
              └──────┬──────┘
                     │
                 ┌───▼───┐
                 │ MySQL │
                 └───────┘
```

### Quem faz o quê

| Parte | Responsabilidade |
|---|---|
| **Frontend (TechZone)** | Telas para o cidadão e para a Defesa Civil (pasta `frontend/`). No perfil Defesa Civil, o navegador conecta ao MCP ("Inspetor MCP") e mostra a análise de risco, a chuva e os sensores reais. |
| **Backend Spring Boot** | Regras de negócio, cadastro e leitura de sensores, canais, barragens, alertas e ocorrências. Único que acessa o MySQL. |
| **MySQL** | Guarda os dados do sistema. |
| **MCP Server (este projeto)** | Expõe *tools* e *resources* para a IA, consulta o backend (só GET) e faz análises determinísticas. |
| **IA (LLM)** | Entende a pergunta do operador, escolhe as tools, combina os resultados e escreve a resposta. |

```text
Usuário (operador da Defesa Civil)
   ↓
IA (assistente)        → interpreta a pergunta e escreve a resposta
   ↓  MCP
MCP Server             → fornece contexto, ferramentas, consultas e análises
   ↓  REST (GET)
Spring Boot API        → regras de negócio
   ↓
MySQL                  → dados
```

---

## 1. O que é o MCP

O **Model Context Protocol** é um protocolo aberto que padroniza como aplicações de IA
se conectam a fontes de dados e ferramentas externas. Um servidor MCP publica:

- **Tools**: funções que a IA pode chamar, com nome, descrição e parâmetros descritos
  em JSON Schema (ex.: `consultar_sensores(status="CRITICO")`).
- **Resources**: documentos somente leitura identificados por URI
  (ex.: `cidade://situacao-atual`), que o aplicativo de IA pode anexar como contexto.

A IA descobre sozinha quais tools existem e quais parâmetros aceitam, sem código
específico para cada IA.

## 2. Papel do MCP no projeto

O MCP é a ponte entre a IA e o sistema da Defesa Civil:

- **fornece contexto**: situação da cidade, sensores, canais, barragens, alertas...
- **fornece ferramentas**: 13 tools de consulta e análise;
- **consulta dados**: sempre pela API do backend, nunca direto no banco;
- **faz análises determinísticas**: saldo de vazão, tendência das leituras e risco
  combinado, com regras fixas e explicáveis.

O MCP **não é um chatbot** e não tem IA própria: interpretar a pergunta e redigir a
resposta em linguagem natural é papel da IA conectada a ele.

## 3. Como instalar

Requisitos: **Python 3.10 ou superior** (testado com 3.14) e o backend Spring Boot
acessível pela rede.

**Jeito mais fácil (Windows):** dê dois cliques em **`iniciar.bat`**. Na primeira vez ele
cria o ambiente virtual `.venv`, instala as dependências e já inicia o servidor.

**Instalação manual:**

```bash
cd mcp-server-anti-enchente
python -m venv .venv

# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
# Linux / macOS
.venv/bin/python -m pip install -r requirements.txt
```

> As bibliotecas ficam **dentro do `.venv`**. Por isso o servidor deve ser iniciado com o
> Python do `.venv` (ou pelo `iniciar.bat`). Rodar só `python main.py` usa o Python do
> sistema, que não tem as bibliotecas, e o servidor avisa "Biblioteca não encontrada".

Dependências principais: `mcp` (SDK oficial, versão 2), `httpx` (requisições ao
backend), `pydantic` (formatos de dados) e `python-dotenv` (leitura do `.env`).

## 4. Como configurar

Copie o arquivo de exemplo e ajuste os valores:

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

| Variável | Padrão | Descrição |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8080` | Endereço da API REST do Spring Boot. |
| `MCP_PORT` | `8000` | Porta do MCP Server (transporte HTTP). |
| `API_TIMEOUT` | `10` | Tempo máximo (segundos) de espera pelo backend. |
| `MCP_HOST` | `127.0.0.1` | Endereço de escuta. `127.0.0.1` aceita só conexões da própria máquina. |
| `MCP_TRANSPORT` | `streamable-http` | `streamable-http` (servidor HTTP) ou `stdio` (a IA inicia o processo). |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` ou `ERROR`. Em `DEBUG`, cada chamada ao backend também é registrada. |
| `LOG_FILE` | *(vazio)* | Arquivo de log, além do terminal (ex.: `logs/mcp.log`). |
| `CORS_ORIGINS` | `http://127.0.0.1:5500,http://localhost:5500` | Endereços do frontend que podem chamar o MCP pelo navegador. |

Toda a configuração é lida em `config.py`; nenhum outro arquivo tem URLs ou portas
escritas diretamente. O `.env` não vai para o Git (está no `.gitignore`).

## 5. Como iniciar o servidor

Com o backend Spring Boot rodando, use um dos jeitos abaixo:

```bash
iniciar.bat                          # Windows: dois cliques ou pelo terminal (.\iniciar.bat)
.venv\Scripts\python.exe main.py     # Windows, pelo terminal
.venv/bin/python main.py             # Linux / macOS
```

O servidor fica disponível em **`http://127.0.0.1:8000/mcp`** (transporte Streamable HTTP):

```text
2026-11-19 16:36:29 | INFO | Backend Spring Boot: http://localhost:8080 (timeout de 10s)
2026-11-19 16:36:29 | INFO | MCP Server iniciado em http://127.0.0.1:8000/mcp
2026-11-19 16:36:29 | INFO | Status no navegador: http://127.0.0.1:8000/
```

**Para conferir se está funcionando**, abra **`http://127.0.0.1:8000/`** no navegador.
A página mostra se o servidor está rodando, o endereço para clientes MCP e se o backend
Spring Boot está respondendo (com o backend desligado, a página demora ~2 s para responder).

O endereço `/mcp` é para **clientes MCP**, não para o navegador: aberto direto, ele
responde `406 Not Acceptable: Client must accept text/event-stream`, **o que é normal**.
Para testar as tools visualmente, use o MCP Inspector (seção 9).

Para aplicativos que iniciam o servidor como processo (ex.: Claude Desktop), use o
transporte `stdio` (veja a seção 9).

### Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `Biblioteca não encontrada: mcp` (ou a janela fecha na hora) | O `main.py` foi aberto com o Python do sistema. Use o `iniciar.bat` ou `.venv\Scripts\python.exe main.py`. |
| Erro 406 ao abrir `/mcp` no navegador | Normal: esse endereço é para clientes MCP. Abra `http://127.0.0.1:8000/` para ver o status. |
| Status mostra `"acessivel": false` no backend | O Spring Boot não está rodando ou o `BACKEND_URL` está errado. As tools responderão "Não foi possível consultar o backend." |
| `address already in use` / porta ocupada | Outro programa usa a porta 8000. Mude `MCP_PORT` no `.env`. |

### Demonstração sem o Spring Boot (backend simulado)

Enquanto o backend real não estiver rodando, a pasta `simulador/` tem um **backend
simulado**: um servidor pequeno que responde às mesmas rotas GET do Spring Boot, com
dados de exemplo de um dia de chuva forte (Centro com previsão de 80 mm, sensor DRN-003 a
93%, Canal Norte a 87% com entrada de 920 m³/h e saída de 640 m³/h, bueiros obstruídos...).

```bash
simulador\iniciar_simulador.bat                     # dois cliques, ou (dentro de mcp-server):
.venv\Scripts\python.exe simulador\backend_simulado.py
```

Ele escuta em `http://127.0.0.1:8080`, o mesmo endereço padrão do Spring Boot, então o
MCP o usa sem nenhuma configuração. O simulador **não faz parte do MCP**: quando o backend
real estiver no ar, feche o simulador (os dois não podem usar a porta 8080 ao mesmo tempo).

### Frontend TechZone conectado ao MCP

O frontend da equipe fica em `frontend/`. Para ver tudo funcionando junto, dê dois cliques em
**`iniciar_demo.bat`** (na raiz do projeto): ele abre três janelas (backend simulado na 8080, MCP Server na 8000 e
frontend na 5500) e abre o navegador em `http://127.0.0.1:5500`.

1. Entre com o perfil **Defesa Civil**.
2. O front conecta sozinho ao MCP: o botão no topo passa a mostrar **"MCP: Live"**.
3. O cartão do painel mostra a **análise de risco do MCP** (`analisar_risco`), a pílula de
   clima mostra a **previsão real** e a aba "Clima & Sensores" lista **sensores, canais,
   barragens e bueiros reais**, com o balanço entrada × saída do canal mais cheio.
4. Clique em "MCP: Live" para abrir o **Inspetor MCP**: ele lista as 13 tools e os 5
   resources do servidor e mostra, em tempo real, cada mensagem JSON-RPC trocada.

Como funciona: `frontend/js/mcp.js` é um **cliente MCP no navegador**. Ele faz o handshake
(`initialize`), descobre as tools (`tools/list`) e chama `tools/call`, atualizando a tela a cada
30 segundos. O servidor libera o endereço do front por CORS (`CORS_ORIGINS`).

| Parte da tela | De onde vêm os dados |
|---|---|
| Análise de risco, clima, sensores, canais, barragens, bueiros | **MCP** (dados do backend) |
| Abrigos, rotas, marcadores fixos do mapa, tela do cidadão | Dados de demonstração do próprio front (ainda não existem no MCP/backend) |
| Pedido de SOS e despacho dos bombeiros | Ações **locais** do front: o MCP é somente leitura, então elas não passam por ele (no futuro, devem ir ao backend com login) |

Se o MCP estiver desligado, o botão mostra "MCP: Offline" e o front continua funcionando com
os dados de demonstração. O front precisa ser aberto por HTTP (`iniciar_front.bat`), não como
arquivo: o servidor MCP recusa páginas abertas direto do disco (`file://`).

## 6. Tools disponíveis

Todas as tools são **somente leitura** (`readOnlyHint: true`).

| Tool | O que faz | Endpoint(s) do backend |
|---|---|---|
| `consultar_situacao_cidade` | Resumo atual: situação geral, sensores, canais e barragens em alerta, alertas ativos, ocorrências abertas. | `GET /api/dashboard/resumo` |
| `consultar_previsao_chuva` | Previsão por região: mm previstos, período e intensidade. Indica se há chuva forte. | `GET /api/previsao-chuva` |
| `consultar_sensores` | Lista os sensores de drenagem, do mais cheio para o mais vazio, com contagem por status. | `GET /api/sensores` |
| `consultar_sensor` | Detalhe de um sensor: código, localização, nível, capacidade, percentual, entrada, saída, status e última atualização. | `GET /api/sensores/{id}` |
| `historico_sensor` | Leituras de um período e análise de tendência (aumento, redução, estabilidade ou dados insuficientes). | `GET /api/sensores/{id}/historico?periodo=24h` |
| `consultar_canais` | Lista os canais com ocupação, vazões e saldo; filtra por situação e por percentual mínimo. | `GET /api/canais` |
| `analisar_fluxo_canal` | Compara entrada e saída de água de um canal (`saldo = entrada - saída`). | `GET /api/canais/{id}` |
| `consultar_bueiros` | Lista os bueiros com localização e situação; filtra por status e região. | `GET /api/bueiros` |
| `consultar_barragens` | Lista as barragens com capacidade, volume, percentual, vazões, nível e status. | `GET /api/barragens` |
| `consultar_areas_risco` | Lista as áreas de risco com região, população estimada, nível de risco e situação. | `GET /api/areas-risco` |
| `consultar_alertas` | Lista os alertas com tipo, mensagem, severidade, região, horário e situação. | `GET /api/alertas/ativos` ou `GET /api/alertas` |
| `consultar_ocorrencias` | Lista as ocorrências da Defesa Civil com localização, descrição, prioridade, tipo, horário e status. | `GET /api/ocorrencias/abertas` ou `GET /api/ocorrencias` |
| `analisar_risco` | **Tool principal.** Combina chuva, sensores, canais, bueiros, barragens, áreas de risco e alertas numa análise estruturada. | as 7 rotas acima, em paralelo |

### Resources

| URI | Conteúdo |
|---|---|
| `cidade://situacao-atual` | Mesmo conteúdo de `consultar_situacao_cidade`. |
| `cidade://alertas-ativos` | Alertas ativos. |
| `cidade://areas-risco` | Áreas de risco. |
| `cidade://sensores` | Todos os sensores. |
| `cidade://barragens` | Todas as barragens. |

## 7. Parâmetros de cada tool

| Tool | Parâmetro | Tipo | Obrigatório | Valores / exemplo |
|---|---|---|---|---|
| `consultar_situacao_cidade` | (nenhum) | | | |
| `consultar_previsao_chuva` | `regiao` | texto | não | `"Centro"`, `"Norte"` |
| `consultar_sensores` | `status` | texto | não | `NORMAL`, `ATENCAO`, `ALERTA`, `CRITICO` |
| `consultar_sensor` | `id` | inteiro ≥ 1 | **sim** | `1` |
| `historico_sensor` | `id` | inteiro ≥ 1 | **sim** | `1` |
| | `periodo` | texto | não (padrão `24h`) | `1h`, `6h`, `12h`, `24h`, `48h`, `7d` |
| `consultar_canais` | `status` | texto | não | `NORMAL`, `ATENCAO`, `ALERTA`, `CRITICO` |
| | `percentual_minimo` | número 0–100 | não | `80` ("acima de 80%") |
| `analisar_fluxo_canal` | `id` | inteiro ≥ 1 | **sim** | `3` |
| `consultar_bueiros` | `status` | texto | não | `NORMAL`, `PARCIALMENTE_OBSTRUIDO`, `OBSTRUIDO` |
| | `regiao` | texto | não | `"Norte"` |
| `consultar_barragens` | `status` | texto | não | `NORMAL`, `ATENCAO`, `ALERTA`, `CRITICO` |
| `consultar_areas_risco` | `nivel` | texto | não | `BAIXO`, `MEDIO`, `ALTO`, `CRITICO` |
| `consultar_alertas` | `apenas_ativos` | booleano | não (padrão `true`) | `true` / `false` |
| `consultar_ocorrencias` | `status` | texto | não (padrão `ABERTA`) | `ABERTA`, `EM_ATENDIMENTO`, `ENCERRADA`, `TODAS` |
| `analisar_risco` | `regiao` | texto | não | `"Norte"` (omita para a cidade inteira) |

Textos de status aceitam minúsculas e acentos (`"obstruído"` vira `OBSTRUIDO`). Valores
fora da lista (quando a lista é fechada) são recusados antes de chegar ao backend.

### Exemplos de resposta

`analisar_fluxo_canal(id=3)`:

```json
{
  "canal": { "id": 3, "nome": "Canal Norte", "percentual": 87.0, "status": "ALERTA", "...": "..." },
  "fluxo": {
    "vazaoEntrada": 920.0,
    "vazaoSaida": 640.0,
    "saldo": 280.0,
    "unidade": "m³/h",
    "resumo": "Entrada: 920 m³/h | Saída: 640 m³/h | Saldo: +280 m³/h",
    "situacaoFluxo": "ACUMULO_POTENCIAL",
    "interpretacao": "A entrada de água está maior que a saída: existe acúmulo potencial de água.",
    "observacao": "Indicador descritivo: sozinho, não permite afirmar que haverá enchente. ..."
  }
}
```

`analisar_risco()`:

```json
{
  "situacao": "ALERTA",
  "nivelConfianca": "ALTO",
  "principaisFatores": [
    "Previsão de chuva forte para Norte (80 mm em 3 horas)",
    "Canal Norte com 87% da capacidade (status ALERTA)",
    "Área de risco ALTO em Região Norte (população estimada: 12.000) com indicadores em alerta",
    "Canal Norte: entrada de água superior à saída (+280 m³/h)"
  ],
  "areasMaisAfetadas": ["Norte"],
  "recomendacao": "Monitorar as regiões destacadas e verificar as áreas de risco próximas aos canais, sensores e bueiros indicados. Acompanhar a vazão dos pontos em que a entrada de água supera a saída.",
  "regiaoAnalisada": null,
  "pontuacao": 6,
  "criterios": { "chuva": 2, "sensores": 0, "canais": 2, "barragens": 0, "bueiros": 0, "alertas": 0, "fluxo": 1, "vulnerabilidade": 1 },
  "escala": "0 = NORMAL · 1 a 3 = ATENÇÃO · 4 a 7 = ALERTA · 8 ou mais = CRÍTICO. ...",
  "fontesConsultadas": ["previsao_chuva", "sensores", "canais", "bueiros", "barragens", "areas_risco", "alertas"],
  "fontesIndisponiveis": [],
  "observacao": "Análise automática baseada em regras fixas, para apoiar a tomada de decisão. ... não constitui ordem de evacuação nem decisão operacional."
}
```

### Como a análise de risco é calculada

Tudo fica em `services/analise_risco.py`, sem IA: os mesmos dados sempre geram o mesmo
resultado. Cada informação é traduzida para uma escala única de gravidade:
**0 = normal, 1 = atenção, 2 = alerta, 3 = crítico**.

| Critério | Nota (0 a 3) |
|---|---|
| Chuva | Pior intensidade prevista: `MODERADA` = 1, `FORTE` = 2, `MUITO_FORTE` = 3. |
| Sensores, canais, barragens | Pior item; vale o maior entre o status e a ocupação (≥ 70% = 1, ≥ 80% = 2, ≥ 90% = 3). |
| Bueiros | `PARCIALMENTE_OBSTRUIDO` = 1, `OBSTRUIDO` = 2 (no máximo 2: um bueiro, sozinho, não torna a situação crítica). |
| Alertas ativos | Pior severidade (`MEDIA` = 1, `ALTA` = 2, `CRITICA` = 3). |
| Fluxo | +1 se um canal ou barragem já cheio (≥ 70% ou status fora do normal) recebe mais água do que escoa. |
| Vulnerabilidade | +1 se uma área de risco `ALTO`/`CRITICO` fica numa região com indicadores em alerta. |

A soma das notas define a situação: **0 = NORMAL · 1 a 3 = ATENÇÃO · 4 a 7 = ALERTA ·
8 ou mais = CRÍTICO**. Qualquer indicador crítico eleva a situação para, no mínimo, ALERTA.

O `nivelConfianca` mede a **completude dos dados**, não a chance de enchente:
`ALTO` com todas as fontes respondendo; `MEDIO` se alguma fonte falhar ou mais de 20%
dos medidores estiver sem leitura; `BAIXO` se 3 ou mais fontes falharem ou não houver
leituras de sensores, canais ou barragens.

A **tendência** (`historico_sensor`) usa a inclinação da reta de mínimos quadrados das
leituras: variação menor que 3% da média é *estabilidade*; acima disso, *tendência de
aumento* ou *de redução*; com menos de 3 leituras, *dados insuficientes*. Exemplo:
`40% → 52% → 67% → 81%` resulta em "O nível do sensor apresentou tendência de aumento
nas últimas leituras." A tendência descreve o passado e não é apresentada como previsão.

## 8. Como o MCP se comunica com o Spring Boot

Toda comunicação passa por **um único arquivo**, `client/backend_client.py`:

- usa HTTP/REST com JSON, na URL definida em `BACKEND_URL`;
- só existe método para **GET**: o cliente não tem como criar, alterar ou apagar dados;
- as rotas ficam no dicionário `ENDPOINTS`; se o backend mudar uma rota, o ajuste é só ali;
- aceita a lista pura (`[...]`) ou a página do Spring Data (`{"content": [...]}`).

### Rotas consultadas (backend da pasta `backend/`)

O MCP usa **só as rotas GET** dos controllers do Spring Boot. Os POST, PUT e DELETE do
backend existem para o frontend e para a administração; o MCP não os chama.

| Rota do backend | Usada por |
|---|---|
| `GET /api/previsoes-chuva` | `consultar_previsao_chuva`, `analisar_risco` |
| `GET /api/sensores` | `consultar_sensores`, `consultar_sensor`, `analisar_risco` |
| `GET /api/canais` | `consultar_canais`, `analisar_fluxo_canal`, `analisar_risco` |
| `GET /api/bueiros` | `consultar_bueiros`, `analisar_risco` |
| `GET /api/barragens` | `consultar_barragens`, `analisar_risco` |
| `GET /api/areas-risco` | `consultar_areas_risco`, `analisar_risco` |
| `GET /api/alertas` | `consultar_alertas`, `analisar_risco` |
| `GET /api/ocorrencias` | `consultar_ocorrencias` |

O backend só tem rotas de **lista**, então o MCP completa o resto sozinho:

| O que falta no backend | O que o MCP faz |
|---|---|
| Busca por id (`/api/sensores/{id}`) | Procura o registro na lista. |
| Alertas ativos / ocorrências abertas | Filtra pelo `status`: tudo que não for ENCERRADO, RESOLVIDO, FINALIZADO, CANCELADO... |
| Resumo da cidade (`/api/dashboard/resumo`) | Calcula a partir das listas (situação geral = item mais grave). Se a rota for criada, o MCP passa a usá-la. |
| Histórico de leituras (`/api/sensores/{id}/historico?periodo=24h`) | `historico_sensor` avisa que o backend ainda não oferece. Basta criar a rota (lista de `{dataHora, nivel}`) para a tendência funcionar. |

### Formato dos dados

`models/schemas.py` converte o JSON das entidades Java no formato que a IA recebe:

| Entidade Java | Campos do backend → nome entregue à IA |
|---|---|
| `PrevisaoChuva` | `local` → `regiao`, `quantidadeChuva` → `chuvaPrevista`, `intensidade`, `dataHora` |
| `SensorDrenagem` | `nome` → `codigo`, `local` → `localizacao`, `nivelAgua` → `nivel`, `status` |
| `Canal` | `nome`, `local` → `localizacao`, `nivelAgua` → `nivel`, `capacidade`, `entradaAgua` → `vazaoEntrada`, `saidaAgua` → `vazaoSaida`, `status` (+ `percentual` e `saldoVazao` calculados) |
| `Bueiro` | `local` → `localizacao`, `status`, `nivelObstrucao`, `ultimaManutencao` → `ultimaAtualizacao` |
| `Barragem` | `nome`, `local` → `localizacao`, `nivelAgua` → `nivel`, `capacidade`, `volumeAtual`, `nivelRisco`, `status` (+ `percentual` calculado) |
| `AreaRisco` | `nome` → `regiao`, `local` → `localizacao`, `tipoRisco`, `nivelRisco`, `descricao`, `status` → `situacaoAtual` |
| `Alerta` | `titulo`, `descricao` → `mensagem`, `nivel` → `severidade`, `local` → `regiao`, `dataHora`, `status` → `situacao` |
| `Ocorrencia` | `tipo`, `descricao`, `local` → `localizacao`, `nivel` → `prioridade`, `dataHora`, `status` |

- Status e níveis são padronizados: `"Crítico"`, `"critico"` e `"CRITICO"` viram `CRITICO`.
- `percentual` = `nivelAgua / capacidade` (canais) ou `volumeAtual / capacidade` (barragens).
  O sensor não tem capacidade no backend, então a gravidade dele vem só do `status`.
- `saldoVazao` (entrada − saída) é calculado pelo MCP; as vazões são tratadas em m³/h.
- Para o cruzamento por região funcionar melhor, o `local` deve conter o nome da região
  (ex.: `"Norte"` ou `"Av. Beira Rio, 180 - Norte"`), igual ao `nome` da área de risco.

### Dados simulados e sensores reais

O MCP não sabe se os dados vêm de sensores físicos ou de uma simulação no backend: ele
só lê a API. Enquanto o backend fornecer dados simulados (ex.: `Sensor DRN-001, nível
82%, entrada 920 m³/h, saída 640 m³/h`), tudo funciona; quando sensores reais forem
integrados ao backend, o MCP continua funcionando sem alterações, desde que o formato
da API se mantenha.

### Tratamento de erros

O MCP nunca inventa dados. Quando algo falha, a tool devolve:

```json
{
  "erro": "Não foi possível consultar o backend.",
  "detalhe": "Serviço temporariamente indisponível."
}
```

| Situação | Mensagem |
|---|---|
| Backend desligado ou erro 5xx | "Não foi possível consultar o backend." |
| Backend não respondeu a tempo | detalhe: "O backend não respondeu em 10 segundos." |
| Registro inexistente (404) | "Sensor 99 não encontrado." |
| JSON em formato inesperado | "O backend retornou dados em formato inesperado." |
| Sensor sem leitura atual | campo `aviso`: "Não foi possível obter a leitura atual do sensor." |

Na `analisar_risco`, se só algumas fontes falharem, a análise usa os dados obtidos,
lista as fontes em `fontesIndisponiveis` e reduz o `nivelConfianca`. Se nenhuma
responder, devolve erro em vez de uma análise vazia.

## 9. Como conectar uma IA compatível

Qualquer aplicativo compatível com MCP descobre as tools automaticamente
(`tools/list`) e recebe as instruções de uso do servidor ao se conectar.

### MCP Inspector (bom para a apresentação)

Ferramenta oficial para ver e testar as tools no navegador:

```bash
python main.py                              # em um terminal
npx @modelcontextprotocol/inspector         # em outro terminal
```

No Inspector, escolha **Streamable HTTP** e a URL `http://127.0.0.1:8000/mcp`.

### Claude Code

Registre o servidor uma vez, rodando o comando dentro da pasta do projeto (ajuste os caminhos):

```bash
claude mcp add anti-enchente --env MCP_TRANSPORT=stdio -- "C:\caminho\projeto\mcp-server\.venv\Scripts\python.exe" "C:\caminho\projeto\mcp-server\main.py"
```

Nesse modo (stdio) o próprio Claude Code inicia o MCP quando precisa; não é preciso deixar
o `iniciar.bat` aberto, apenas o backend (real ou simulado). Confira com `claude mcp list`:
deve aparecer `anti-enchente ... ✔ Connected`. Depois, **abra uma conversa nova** (as tools
são carregadas no início da conversa) e pergunte, por exemplo, "Existe risco de enchente
agora? Quais regiões precisam de mais atenção?". Na primeira vez, o Claude pede permissão
para usar as tools do `anti-enchente`.

Para usar o servidor HTTP já iniciado (`iniciar.bat`), registre pela URL:

```bash
claude mcp add --transport http anti-enchente http://127.0.0.1:8000/mcp
```

Para remover: `claude mcp remove anti-enchente`.

### Claude Desktop (stdio)

Em *Settings → Developer → Edit Config*, adicione (ajuste os caminhos):

```json
{
  "mcpServers": {
    "anti-enchente": {
      "command": "C:\\caminho\\mcp-server-anti-enchente\\.venv\\Scripts\\python.exe",
      "args": ["C:\\caminho\\mcp-server-anti-enchente\\main.py"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "BACKEND_URL": "http://localhost:8080"
      }
    }
  }
}
```

### Outros clientes ou código próprio

Use o endereço `http://127.0.0.1:8000/mcp` (Streamable HTTP). Com o SDK Python:

```python
import asyncio
from mcp import Client

async def main():
    async with Client("http://127.0.0.1:8000/mcp") as cliente:
        resultado = await cliente.call_tool("analisar_risco", {"regiao": "Norte"})
        print(resultado.structured_content)

asyncio.run(main())
```

## 10. Exemplos de perguntas

| Pergunta | Tools que a IA tende a usar |
|---|---|
| "Qual a situação atual da cidade?" | `consultar_situacao_cidade` |
| "Quais sensores estão em situação crítica?" | `consultar_sensores(status="CRITICO")` |
| "Existe previsão de chuva forte?" | `consultar_previsao_chuva` |
| "Qual canal está com maior nível?" | `consultar_canais` (o primeiro da lista) |
| "Existe algum canal onde a entrada de água seja maior que a saída?" | `consultar_canais` (`canaisComEntradaMaiorQueSaida`) e `analisar_fluxo_canal` |
| "Quais áreas possuem maior risco?" | `consultar_areas_risco` |
| "Quantos alertas estão ativos?" | `consultar_alertas` |
| "Qual barragem está com maior percentual?" | `consultar_barragens` |
| "Existe algum bueiro obstruído próximo a uma área de risco?" | `consultar_bueiros(status="OBSTRUIDO")` + `consultar_areas_risco` |
| "Há tendência de aumento no nível dos canais?" | `consultar_sensores` + `historico_sensor` |
| "Quais regiões precisam de maior atenção neste momento?" | `analisar_risco` (`areasMaisAfetadas`) |
| "Existe risco de alagamento na região Norte?" | `analisar_risco(regiao="Norte")`, `consultar_previsao_chuva`, `consultar_canais`, `consultar_bueiros(regiao="Norte")`... |

---

## Segurança

- **Somente consulta**: nenhuma tool altera sensores, barragens, canais, alertas,
  ocorrências ou o banco. O cliente HTTP só tem método GET, e as tools são anunciadas
  à IA como `readOnlyHint: true`.
- **Sem acesso ao banco**: o MCP não tem credenciais do MySQL; tudo passa pela API.
- **Sem decisões operacionais**: as análises não emitem ordens de evacuação; a
  recomendação é de monitoramento e a decisão fica com a Defesa Civil.
- **Parâmetros validados**: ids são inteiros positivos (não alteram a URL), e status,
  níveis e períodos só aceitam valores da lista.
- **Rede local por padrão**: o servidor escuta em `127.0.0.1`. Para expor em outra
  máquina, coloque autenticação na frente (o SDK MCP suporta OAuth).
- **Erros sem detalhes internos**: rastros de erro ficam só no log do servidor.
- **Ferramentas de escrita no futuro**: se forem criadas, devem exigir autenticação e
  autorização do operador (ex.: token validado pelo Spring Security) e confirmação humana.

## Logs

Cada chamada gera uma linha com ferramenta, horário, parâmetros, resultado e tempo:

```text
2026-11-19 16:16:46 | INFO | ferramenta=analisar_fluxo_canal | parametros={"id": 3} | resultado=sucesso | tempo=7ms
2026-11-19 16:16:51 | WARNING | ferramenta=consultar_situacao_cidade | parametros={} | resultado=erro (Não foi possível consultar o backend. Serviço temporariamente indisponível.) | tempo=2295ms
```

As respostas do backend não são registradas. Parâmetros com nomes sensíveis (senha,
token...) aparecem como `***`, e textos longos são cortados. Os logs vão para o
terminal (stderr) e, se `LOG_FILE` estiver definido, também para um arquivo.

## Testes

```bash
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

Os testes usam um backend simulado em memória (`tests/dados_simulados.py`), sem precisar
do Spring Boot. Eles cobrem as regras de análise, todas as tools, os erros do backend, o
log e o servidor MCP completo acessado por um cliente MCP real.

## Estrutura da pasta `mcp-server/`

```text
mcp-server/
├── iniciar.bat              # inicia o servidor no Windows (cria o .venv na 1ª vez)
├── main.py                  # cria o servidor MCP e registra tools, resources e a página de status
├── config.py                # lê BACKEND_URL, MCP_PORT, API_TIMEOUT (e opcionais)
├── requirements.txt         # dependências do servidor
├── requirements-dev.txt     # dependências dos testes
├── .env.example             # modelo de configuração, sem credenciais
├── client/
│   └── backend_client.py    # único ponto que chama o Spring Boot (só GET)
├── tools/
│   ├── chuva.py             # consultar_previsao_chuva
│   ├── sensores.py          # consultar_sensores, consultar_sensor, historico_sensor
│   ├── canais.py            # consultar_canais, analisar_fluxo_canal
│   ├── bueiros.py           # consultar_bueiros
│   ├── barragens.py         # consultar_barragens
│   ├── areas_risco.py       # consultar_areas_risco
│   ├── alertas.py           # consultar_alertas
│   ├── ocorrencias.py       # consultar_ocorrencias
│   └── risco.py             # consultar_situacao_cidade, analisar_risco
├── services/
│   └── analise_risco.py     # regras de fluxo, tendência, resumo e risco (sem IA, sem backend)
├── models/
│   └── schemas.py           # formatos de entrada e saída (status, níveis, análises)
├── resources/
│   └── cidade.py            # cidade://situacao-atual, alertas-ativos, areas-risco, sensores, barragens
├── utils/
│   └── logs.py              # log de ferramenta, horário, parâmetros, sucesso/erro e tempo
├── simulador/               # NÃO faz parte do MCP: imita o Spring Boot nas demonstrações
│   ├── backend_simulado.py  # mesmas rotas GET e mesmos campos do backend real
│   └── iniciar_simulador.bat
└── tests/                   # testes automatizados com backend simulado
```
