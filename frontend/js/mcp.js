/**
 * INTEGRAÇÃO DO FRONTEND TECHZONE COM O MCP SERVER (Model Context Protocol)
 *
 * O navegador funciona como um cliente MCP:
 *   1. "initialize" (handshake) -> o servidor devolve um id de sessão;
 *   2. "tools/list" e "resources/list" -> descobre as ferramentas disponíveis;
 *   3. "tools/call" -> consulta sensores, canais, chuva e a análise de risco.
 *
 * Modos:
 *   - 'live': conectado ao MCP Server (python main.py) -> dados reais do backend.
 *   - 'mock': sem MCP -> o front usa os dados de demonstração escritos no HTML.
 *
 * Regra de segurança: o MCP é SOMENTE LEITURA. Ações como pedir SOS e despachar
 * bombeiros continuam locais no front (no futuro devem ir ao backend, com login).
 */

const MCP_ENDPOINT_PADRAO = 'http://127.0.0.1:8000/mcp';
const MCP_VERSAO_PROTOCOLO = '2025-11-25';
const MCP_INTERVALO_ATUALIZACAO_MS = 30000;

// Posição aproximada de cada região no mapa vetorial do front (para os marcadores).
const POSICAO_DAS_REGIOES = {
  CENTRO: { x: 505, y: 382 },
  NORTE: { x: 460, y: 160 },
  SUL: { x: 460, y: 610 },
  LESTE: { x: 900, y: 380 },
  OESTE: { x: 215, y: 520 },
};

// Dados de demonstração do HTML, guardados para voltar a eles ao sair do modo live.
const SENSORES_DEMONSTRACAO = SENSORS_DATA.slice();

function escaparHtml(valor) {
  return String(valor ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

function normalizarTexto(valor) {
  return String(valor ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().trim();
}

function rotulo(codigo) {
  const rotulos = { ATENCAO: 'Atenção', CRITICO: 'Crítico', ALERTA: 'Alerta', NORMAL: 'Normal', MUITO_FORTE: 'Muito Forte',
    FORTE: 'Forte', MODERADA: 'Moderada', FRACA: 'Fraca', MEDIO: 'Médio', ALTO: 'Alto', BAIXO: 'Baixo', MEDIA: 'Média', ALTA: 'Alta', ALAGAMENTO: 'Alagamento', DESLIZAMENTO: 'Deslizamento', EM_MONITORAMENTO: 'Em monitoramento', OBSTRUIDO: 'Obstruído', PARCIALMENTE_OBSTRUIDO: 'Parcialmente obstruído' };
  return rotulos[codigo] || String(codigo ?? '').replace(/_/g, ' ');
}

function numero(valor) {
  return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
}

function definirTexto(id, texto) {
  const el = document.getElementById(id);
  if (el) el.textContent = texto;
}

// =====================================================================
// 1. CLIENTE MCP (JSON-RPC 2.0 sobre Streamable HTTP)
// =====================================================================
window.HydroMCP = {
  mode: 'mock', // 'mock' | 'live'
  endpoint: MCP_ENDPOINT_PADRAO,
  sessionId: null,
  proximoId: 1,
  logs: [],
  tools: [],
  resources: [],
  timerAtualizacao: null,

  logRpc(direction, payload) {
    const entry = `[${new Date().toLocaleTimeString('pt-BR')}] ${direction}\n${JSON.stringify(payload, null, 2)}`;
    this.logs.unshift(entry.length > 2500 ? `${entry.slice(0, 2500)}\n...` : entry);
    if (this.logs.length > 12) this.logs.pop();
    const logEl = document.getElementById('mcpRpcLogOutput');
    if (logEl) logEl.textContent = this.logs.join('\n\n');
  },

  /** Envia uma mensagem JSON-RPC. A resposta pode vir em JSON ou em SSE (text/event-stream). */
  async enviar(metodo, params = {}, { notificacao = false } = {}) {
    const mensagem = { jsonrpc: '2.0', method: metodo, params };
    if (!notificacao) mensagem.id = this.proximoId++;

    const headers = { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream' };
    if (this.sessionId) {
      headers['mcp-session-id'] = this.sessionId;
      headers['mcp-protocol-version'] = MCP_VERSAO_PROTOCOLO;
    }

    const resposta = await fetch(this.endpoint, { method: 'POST', headers, body: JSON.stringify(mensagem) });
    if (metodo === 'initialize') this.sessionId = resposta.headers.get('mcp-session-id');
    if (notificacao) return null;
    if (!resposta.ok) throw new Error(`O MCP respondeu HTTP ${resposta.status}`);

    const tipo = resposta.headers.get('content-type') || '';
    const texto = await resposta.text();
    const dados = tipo.includes('text/event-stream')
      ? texto.split('\n').filter((l) => l.startsWith('data:')).map((l) => JSON.parse(l.slice(5))).find((m) => m.id === mensagem.id)
      : JSON.parse(texto);
    if (!dados) throw new Error('Resposta do MCP vazia.');
    if (dados.error) throw new Error(dados.error.message || 'Erro do MCP');
    return dados.result;
  },

  /** Handshake + descoberta das tools e resources do servidor. */
  async conectar() {
    this.sessionId = null;
    const inicio = await this.enviar('initialize', {
      protocolVersion: MCP_VERSAO_PROTOCOLO,
      capabilities: {},
      clientInfo: { name: 'techzone-frontend', version: '1.0.0' },
    });
    await this.enviar('notifications/initialized', {}, { notificacao: true });
    this.tools = (await this.enviar('tools/list')).tools || [];
    this.resources = (await this.enviar('resources/list')).resources || [];
    this.logRpc('← MCP CONECTADO', { servidor: inicio.serverInfo, tools: this.tools.map((t) => t.name), resources: this.resources.map((r) => r.uri) });
    return inicio;
  },

  /** Chama uma tool e devolve o resultado estruturado (JSON). */
  async callTool(toolName, args = {}) {
    if (this.mode !== 'live') return null;
    this.logRpc('→ MCP REQUEST (tools/call)', { name: toolName, arguments: args });
    let result;
    try {
      result = await this.enviar('tools/call', { name: toolName, arguments: args });
    } catch (err) {
      // Sessão expirada (servidor reiniciado): refaz o handshake uma vez.
      if (!String(err.message).includes('404')) throw err;
      await this.conectar();
      result = await this.enviar('tools/call', { name: toolName, arguments: args });
    }
    const dados = result.structuredContent ?? JSON.parse(result.content?.[0]?.text || '{}');
    this.logRpc(`← MCP RESPONSE (${toolName})`, dados);
    if (result.isError) throw new Error(result.content?.[0]?.text || `Falha na tool ${toolName}`);
    return dados;
  },

  async readResource(uri) {
    if (this.mode !== 'live') return null;
    this.logRpc('→ MCP REQUEST (resources/read)', { uri });
    const result = await this.enviar('resources/read', { uri });
    const dados = JSON.parse(result.contents?.[0]?.text || '{}');
    this.logRpc(`← MCP RESOURCE (${uri})`, dados);
    return dados;
  },

  /** Ações de escrita não passam pelo MCP (somente leitura): ficam registradas como locais. */
  registrarAcaoLocal(acao, dados) {
    this.logRpc(`• AÇÃO LOCAL (não enviada ao MCP, que é somente leitura): ${acao}`, dados);
  },
};

// =====================================================================
// 2. CONEXÃO, PAINEL DO INSPETOR E ATUALIZAÇÃO DA TELA
// =====================================================================
function toggleMcpDrawer(forceState) {
  const drawer = document.getElementById('mcpInspectorDrawer');
  if (!drawer) return;
  const shouldOpen = typeof forceState === 'boolean' ? forceState : drawer.classList.contains('hidden');
  drawer.classList.toggle('hidden', !shouldOpen);
}

function atualizarIndicadorMcp(estado, detalhe) {
  const estilos = {
    live: ['MCP: Live', 'w-2 h-2 rounded-full bg-petrol-300 animate-pulse'],
    conectando: ['MCP: Conectando...', 'w-2 h-2 rounded-full bg-signal-amber animate-pulse'],
    mock: ['MCP: Simulado', 'w-2 h-2 rounded-full bg-slate-400'],
    erro: ['MCP: Offline', 'w-2 h-2 rounded-full bg-signal-coral'],
  };
  const [texto, classe] = estilos[estado];
  ['', 'Mobile'].forEach((sufixo) => {
    definirTexto(`mcpStatusLabel${sufixo}`, texto);
    const dot = document.getElementById(`mcpStatusDot${sufixo}`);
    if (dot) dot.className = classe;
  });
  definirTexto('mcpConexaoDetalhe', detalhe || '');
}

function renderizarListasDoInspetor() {
  const tools = document.getElementById('mcpToolsList');
  const resources = document.getElementById('mcpResourcesList');
  if (tools && HydroMCP.tools.length) {
    tools.innerHTML = HydroMCP.tools.map((t) => `<li title="${escaparHtml(t.description)}">• ${escaparHtml(t.name)}()</li>`).join('');
  }
  if (resources && HydroMCP.resources.length) {
    resources.innerHTML = HydroMCP.resources.map((r) => `<li>• ${escaparHtml(r.uri)}</li>`).join('');
  }
}

async function setMcpConnectionMode(mode, { silencioso = false } = {}) {
  const inputEl = document.getElementById('mcpEndpointInput');
  if (inputEl && inputEl.value.trim()) HydroMCP.endpoint = inputEl.value.trim();
  clearInterval(HydroMCP.timerAtualizacao);

  if (mode !== 'live') {
    HydroMCP.mode = 'mock';
    restaurarDadosDeDemonstracao();
    atualizarIndicadorMcp('mock', 'Usando os dados de demonstração do próprio front.');
    if (!silencioso) showToast('Conector MCP em modo de simulação local.');
    return;
  }

  atualizarIndicadorMcp('conectando', `Conectando a ${HydroMCP.endpoint}...`);
  try {
    HydroMCP.mode = 'live';
    const inicio = await HydroMCP.conectar();
    renderizarListasDoInspetor();
    await carregarDadosDoMcp();
    HydroMCP.timerAtualizacao = setInterval(() => carregarDadosDoMcp().catch(() => {}), MCP_INTERVALO_ATUALIZACAO_MS);
    atualizarIndicadorMcp('live', `Conectado a ${inicio.serverInfo?.name || 'MCP'} • ${HydroMCP.tools.length} tools • atualiza a cada 30 s`);
    if (!silencioso) showToast(`MCP conectado: dados reais via ${HydroMCP.endpoint}`);
  } catch (err) {
    HydroMCP.mode = 'mock';
    restaurarDadosDeDemonstracao();
    atualizarIndicadorMcp('erro', `Não foi possível conectar (${err.message}). Inicie o MCP com iniciar.bat. Mostrando dados de demonstração.`);
    HydroMCP.logRpc('← MCP OFFLINE', { erro: err.message, endpoint: HydroMCP.endpoint });
    if (!silencioso) showToast('MCP offline: mostrando dados de demonstração.');
  }
}

async function testMcpResourceSync() {
  if (HydroMCP.mode !== 'live') {
    showToast('Conecte o MCP (Conectar Live) para testar.');
    return;
  }
  await HydroMCP.readResource('cidade://situacao-atual');
  showToast('Resource cidade://situacao-atual lido. Veja o log abaixo.');
}

async function executarAnaliseDeRiscoMcp() {
  if (HydroMCP.mode !== 'live') {
    showToast('Conecte o MCP (Conectar Live) para executar a análise.');
    return;
  }
  const analise = await HydroMCP.callTool('analisar_risco');
  renderizarRiscoCivil(analise, null);
  showToast(`Análise de risco: situação ${rotulo(analise.situacao)}.`);
}

// =====================================================================
// 3. DADOS REAIS (MCP) -> TELA
// =====================================================================
async function carregarDadosDoMcp() {
  const [previsao, sensores, canais, barragens, bueiros, risco, areas] = await Promise.all([
    HydroMCP.callTool('consultar_previsao_chuva'),
    HydroMCP.callTool('consultar_sensores'),
    HydroMCP.callTool('consultar_canais'),
    HydroMCP.callTool('consultar_barragens'),
    HydroMCP.callTool('consultar_bueiros'),
    HydroMCP.callTool('analisar_risco'),
    HydroMCP.callTool('consultar_areas_risco'),
  ]);
  const erro = [previsao, sensores, canais, barragens, bueiros, risco].find((r) => r && r.erro);
  if (erro) {
    atualizarIndicadorMcp('erro', `${erro.erro} ${erro.detalhe || ''} O backend está rodando?`);
    return;
  }
  renderizarClima(previsao, canais);
  renderizarSensores(sensores, canais, barragens, bueiros);
  renderizarRiscoCivil(risco, areas, sensores);
  definirMapaAoVivo(true);
  desenharRiscoNoMapa(SENSORS_DATA, risco);
}

function posicaoNoMapa(item, indice) {
  const texto = normalizarTexto(item.regiao || item.localizacao);
  const regiao = Object.keys(POSICAO_DAS_REGIOES).find((nome) => texto.includes(nome));
  const base = POSICAO_DAS_REGIOES[regiao] || { x: 540, y: 445 };
  return { x: base.x + (indice % 3) * 18, y: base.y + Math.floor(indice / 3) * 14 };
}

function statusVisual(status, temLeitura = true) {
  if (!temLeitura) return 'fault';
  if (status === 'CRITICO') return 'critical';
  if (status === 'ALERTA' || status === 'ATENCAO' || String(status).includes('OBSTRUIDO')) return 'warning';
  return 'normal';
}

function renderizarClima(previsao, canais) {
  const previsoes = previsao?.previsoes || [];
  const principal = previsoes[0]; // a tool já ordena da mais intensa para a mais fraca
  const canal = (canais?.canais || [])[0]; // e os canais do mais cheio para o mais vazio

  if (!principal) {
    definirTexto('weatherCivilSummaryText', 'Sem previsão de chuva cadastrada');
    ['weatherCivilIntensidade', 'weatherCivilDuracao', 'weatherCivilAcumulado', 'climaVolume', 'climaIntensidade', 'climaDuracao', 'climaAcumulado']
      .forEach((id) => definirTexto(id, '—'));
    definirTexto('weatherCivilNota', 'Fonte: MCP • consultar_previsao_chuva. O backend não retornou nenhuma previsão.');
    definirTexto('climaChuvaStatus', 'Sem previsão cadastrada');
  }

  if (principal) {
    const mm = principal.chuvaPrevista != null ? `${numero(principal.chuvaPrevista)} mm` : 'sem volume';
    const quando = principal.periodo || (principal.dataHora
      ? `até ${new Date(principal.dataHora).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
      : '—');
    definirTexto('weatherCivilSummaryText', `Chuva ${rotulo(principal.intensidade)} • ${mm} (${principal.regiao || 'cidade'})`);
    definirTexto('weatherCivilIntensidade', rotulo(principal.intensidade));
    definirTexto('weatherCivilDuracaoLabel', 'Previsão');
    definirTexto('weatherCivilDuracao', quando);
    definirTexto('weatherCivilAcumuladoLabel', 'Previsto');
    definirTexto('weatherCivilAcumulado', mm);
    definirTexto('weatherCivilNota', `Fonte: MCP • consultar_previsao_chuva. Região com maior previsão: ${principal.regiao || 'cidade'}.`);

    definirTexto('climaChuvaStatus', previsao.haPrevisaoChuvaForte ? 'Chuva forte prevista' : 'Sem chuva forte prevista');
    definirTexto('climaVolumeLabel', `Previsto • ${principal.regiao || 'cidade'}`);
    definirTexto('climaVolume', mm);
    definirTexto('climaIntensidade', rotulo(principal.intensidade));
    definirTexto('climaDuracaoLabel', 'Previsão');
    definirTexto('climaDuracao', quando);
    definirTexto('climaAcumuladoLabel', 'Regiões com previsão');
    definirTexto('climaAcumulado', String(previsoes.length));
  }

  if (!canal) {
    definirTexto('weatherCivilCargaTexto', 'Nenhum canal cadastrado');
    ['weatherCivilCargaBarra', 'fluxoEntradaBarra', 'fluxoSaidaBarra'].forEach((id) => { document.getElementById(id).style.width = '0%'; });
    definirTexto('fluxoTitulo', 'Sem canais');
    definirTexto('fluxoEntrada', '—');
    definirTexto('fluxoSaida', '—');
    definirTexto('fluxoNota', 'Nenhum canal cadastrado no backend: não há vazão de entrada e saída para comparar.');
  }

  if (canal) {
    const pct = canal.percentual ?? 0;
    definirTexto('weatherCivilCargaTexto', `${numero(pct)}% • ${canal.nome || 'canal'} (${rotulo(canal.status)})`);
    const barra = document.getElementById('weatherCivilCargaBarra');
    if (barra) barra.style.width = `${Math.min(pct, 100)}%`;

    const entrada = canal.vazaoEntrada ?? 0;
    const saida = canal.vazaoSaida ?? 0;
    const maior = Math.max(entrada, saida, 1);
    definirTexto('fluxoTitulo', `${canal.nome}: ${numero(pct)}%`);
    definirTexto('fluxoEntradaLabel', 'Entrada de água no canal');
    definirTexto('fluxoEntrada', `${numero(entrada)} m³/h`);
    definirTexto('fluxoSaidaLabel', 'Saída (escoamento) do canal');
    definirTexto('fluxoSaida', `${numero(saida)} m³/h`);
    document.getElementById('fluxoEntradaBarra').style.width = `${(entrada / maior) * 100}%`;
    document.getElementById('fluxoSaidaBarra').style.width = `${(saida / maior) * 100}%`;
    const saldo = canal.saldoVazao ?? entrada - saida;
    definirTexto('fluxoNota', saldo > 0
      ? `Entrada maior que a saída (+${numero(saldo)} m³/h): acúmulo potencial de água. Indicador descritivo, não é previsão de enchente.`
      : `Saída maior ou igual à entrada (${numero(saldo)} m³/h): o canal está escoando.`);
  }
}

function renderizarSensores(sensores, canais, barragens, bueiros) {
  const itens = [];
  (sensores?.sensores || []).forEach((s) => itens.push({
    ...s, nomeTela: `Sensor ${s.codigo || s.id}`, tipo: 'Sensor de Nível', idTela: `SENSOR-${s.id}`,
  }));
  (canais?.canais || []).forEach((c) => itens.push({ ...c, nomeTela: c.nome, tipo: 'Canal de Drenagem', idTela: `CANAL-${c.id}` }));
  (barragens?.barragens || []).forEach((b) => itens.push({ ...b, nomeTela: b.nome, tipo: 'Barragem / Reservatório', idTela: `BAR-${b.id}` }));
  (bueiros?.bueiros || []).filter((b) => b.status !== 'NORMAL').forEach((b) => itens.push({
    ...b, nomeTela: `Bueiro • ${b.localizacao || ''}`, tipo: 'Bueiro', idTela: b.codigo || `BUEIRO-${b.id}`, ehBueiro: true,
  }));

  const dados = itens.map((item, i) => {
    const temLeitura = item.ehBueiro || item.percentual != null || item.nivel != null;
    const posicao = posicaoNoMapa(item, i);
    const local = item.regiao || item.localizacao || '';
    let fluxo = '—';
    if (item.vazaoEntrada != null && item.vazaoSaida != null) fluxo = `${numero(item.vazaoEntrada)} / ${numero(item.vazaoSaida)} m³/h`;
    else if (item.ehBueiro && item.nivelObstrucao != null) fluxo = `Obstrução ${numero(item.nivelObstrucao)}%`;
    let leitura = 'Sem leitura';
    if (item.ehBueiro) leitura = rotulo(item.status);
    else if (item.percentual != null) leitura = `${numero(item.percentual)}%`;
    else if (item.nivel != null) leitura = `Nível ${numero(item.nivel)} m`;
    return {
      id: escaparHtml(item.idTela),
      name: escaparHtml(item.nomeTela),
      type: item.tipo,
      capacity: escaparHtml(leitura),
      flow: escaparHtml(fluxo),
      status: statusVisual(item.status, temLeitura),
      statusLabel: temLeitura ? `${escaparHtml(rotulo(item.status))} • ${escaparHtml(local)}` : 'Sem leitura atual — vistoria recomendada',
      x: posicao.x,
      y: posicao.y,
    };
  });

  SENSORS_DATA.splice(0, SENSORS_DATA.length, ...dados);
  definirTexto('sensorRoleNote', `Dados reais via MCP • ${new Date().toLocaleTimeString('pt-BR')}`);
  renderSensorsTab();
  const lista = document.getElementById('sensorsListContainer');
  if (lista && dados.length === 0) {
    lista.innerHTML = '<p class="md:col-span-2 p-4 rounded-2xl bg-abyss-950/70 border border-white/10 text-xs text-slate-300">Nenhum sensor, canal, barragem ou bueiro cadastrado no backend ainda.</p>';
  }
}

function renderizarRiscoCivil(risco, areas, sensores) {
  const lista = document.getElementById('painelCivilRiskList');
  if (!lista || !risco || risco.erro) return;

  const corDaSituacao = { CRITICO: 'text-signal-coral', ALERTA: 'text-signal-amber', ATENCAO: 'text-signal-amber', NORMAL: 'text-petrol-300' };
  definirTexto('painelCivilRiskTitle', `Análise de risco (MCP) • ${rotulo(risco.situacao)}`);
  definirTexto('painelCivilConfianca', `Confiança ${rotulo(risco.nivelConfianca)}`);

  const areasPorNome = {};
  (areas?.areas || []).forEach((a) => { areasPorNome[normalizarTexto(a.regiao)] = a; });

  const linhasAreas = (risco.areasMaisAfetadas || []).slice(0, 3).map((nome, i) => {
    const area = areasPorNome[normalizarTexto(nome)];
    const posicao = posicaoNoMapa({ regiao: nome }, 0);
    let detalhe = 'Indicadores em alerta';
    if (area) {
      const extra = area.populacaoEstimada ? `${numero(area.populacaoEstimada)} hab.` : rotulo(area.tipoRisco || '');
      detalhe = [extra, `risco ${rotulo(area.nivelRisco)}`].filter(Boolean).join(' • ');
    }
    return `
      <div onclick="focusSvgPoint(${posicao.x}, ${posicao.y})"
           class="cursor-pointer flex items-center justify-between gap-3 p-2.5 rounded-2xl bg-abyss-950/75 hover:bg-abyss-900 border ${i === 0 ? 'border-signal-coral/35' : 'border-white/10'} transition">
        <div class="min-w-0">
          <span class="font-semibold text-white block truncate">${i + 1}. ${escaparHtml(nome)}</span>
          <span class="text-slate-400 tabular">${escaparHtml(detalhe)}</span>
        </div>
        <span class="${i === 0 ? corDaSituacao[risco.situacao] || 'text-signal-amber' : 'text-signal-amber'} font-semibold shrink-0">${i === 0 ? rotulo(risco.situacao) : 'Atenção'}</span>
      </div>`;
  }).join('');

  const fatores = (risco.principaisFatores || []).slice(0, 3)
    .map((f) => `<li class="leading-snug">• ${escaparHtml(f)}</li>`).join('');

  lista.innerHTML = `${linhasAreas || '<p class="text-slate-400">Nenhuma área em alerta.</p>'}
    <ul class="pt-1 space-y-1 text-[11px] text-slate-300">${fatores}</ul>
    <p class="text-[11px] text-slate-400 leading-relaxed">${escaparHtml(risco.recomendacao)}</p>`;

  const semLeitura = (sensores?.sensores || []).filter((s) => s.percentual == null && s.nivel == null);
  definirTexto('painelCivilFalhaTexto', semLeitura.length
    ? `Falha de telemetria: ${semLeitura.map((s) => `${s.codigo || s.id} (${s.localizacao || s.regiao || '—'})`).join(', ')}`
    : ((sensores?.sensores || []).length ? 'Todos os sensores com leitura atual' : 'Nenhum sensor cadastrado no backend'));
}

// =====================================================================
// 4. MAPA: RISCOS REAIS NO LUGAR DOS DESENHOS DE DEMONSTRAÇÃO
// =====================================================================
function definirMapaAoVivo(ativo) {
  document.querySelectorAll('.demo-risco').forEach((el) => el.classList.toggle('hidden', ativo));
  const camada = document.getElementById('svgLiveRiskLayer');
  if (camada && !ativo) camada.innerHTML = '';
}

function desenharRiscoNoMapa(itens, risco) {
  const camada = document.getElementById('svgLiveRiskLayer');
  if (!camada) return;

  // Brilho vermelho sobre as regiões que a análise do MCP aponta como mais afetadas.
  const brilho = risco && risco.situacao !== 'NORMAL'
    ? (risco.areasMaisAfetadas || []).map((nome) => {
        const p = posicaoNoMapa({ regiao: nome }, 0);
        return `<circle cx="${p.x}" cy="${p.y}" r="115" fill="url(#dangerHeatGrad)" />`;
      }).join('')
    : '';

  // Marcadores dos itens fora do normal (os mais graves primeiro; no máximo 8 para não poluir o mapa).
  const cores = { critical: '#FF3B5C', warning: '#FFB020', fault: '#FFB020' };
  const ordem = { critical: 0, warning: 1, fault: 2 };
  const marcadores = itens.filter((i) => i.status !== 'normal')
    .sort((a, b) => ordem[a.status] - ordem[b.status]).slice(0, 8)
    .map((i) => `
      <g transform="translate(${i.x}, ${i.y})" class="cursor-pointer" onclick="focusSvgPoint(${i.x}, ${i.y})">
        <circle r="15" fill="${cores[i.status]}" opacity="0.28" class="svg-pulse-ring" />
        <circle r="7" fill="${cores[i.status]}" stroke="#050B16" stroke-width="2.5" />
        <g transform="translate(13, -17)">
          <rect width="196" height="38" rx="10" fill="rgba(10,21,41,0.92)" stroke="${cores[i.status]}" stroke-opacity="0.6" />
          <text x="10" y="16" fill="${cores[i.status]}" font-size="10.5" font-weight="700">${i.name}</text>
          <text x="10" y="30" fill="#94A3B8" font-size="9.5">${i.capacity} • ${i.statusLabel}</text>
        </g>
      </g>`).join('');

  camada.innerHTML = brilho + marcadores;
}

function restaurarDadosDeDemonstracao() {
  definirMapaAoVivo(false);
  SENSORS_DATA.splice(0, SENSORS_DATA.length, ...SENSORES_DEMONSTRACAO);
  if (typeof renderSensorsTab === 'function') renderSensorsTab();
}

// Ao entrar como Defesa Civil, tenta conectar ao MCP automaticamente (sem incomodar se estiver offline).
document.addEventListener('submit', (evento) => {
  if (evento.target && evento.target.closest('#loginScreen') && appState.loginSelectedRole === 'civil' && HydroMCP.mode !== 'live') {
    setTimeout(() => setMcpConnectionMode('live', { silencioso: true }), 0);
  }
});
