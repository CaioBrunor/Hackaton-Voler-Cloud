/**
 * ASSISTENTE DE IA (Claude) DO SITE
 *
 * Painel de chat com um "painel de perguntas": perguntas prontas, por assunto, que o usuário
 * clica para o Claude responder usando os dados do MCP Server (sensores, canais, alertas...).
 * O usuário também pode digitar uma pergunta livre.
 *
 *   Navegador  ->  assistente (porta 8100)  ->  API do Claude  <->  MCP Server  ->  backend
 *
 * A chave da API fica só no servidor do assistente: este arquivo nunca a vê.
 * O assistente só consulta dados; pedir SOS e despachar equipes continuam sendo ações do painel.
 */

(function () {
  const ASSISTENTE_URL = (window.ASSISTENTE_URL || 'http://127.0.0.1:8100').replace(/\/$/, '');

  // ===================================================================
  // PAINEL DE PERGUNTAS: o que cada perfil pode perguntar com um clique
  // ===================================================================
  const PERGUNTAS = {
    defesa_civil: [
      { titulo: 'Visão geral', perguntas: [
        'Qual a situação atual da cidade?',
        'Quais regiões precisam de maior atenção neste momento?',
        'Quantos alertas estão ativos e quais são os mais graves?',
      ] },
      { titulo: 'Chuva', perguntas: [
        'Existe previsão de chuva forte?',
        'Qual região terá mais chuva nas próximas horas?',
      ] },
      { titulo: 'Sensores e canais', perguntas: [
        'Quais sensores estão em situação crítica?',
        'Qual canal está com maior nível?',
        'Existe algum canal onde a entrada de água seja maior que a saída?',
      ] },
      { titulo: 'Bueiros e barragens', perguntas: [
        'Existe algum bueiro obstruído?',
        'Existe algum bueiro obstruído próximo a uma área de risco?',
        'Qual barragem está com maior percentual?',
      ] },
      { titulo: 'Áreas de risco', perguntas: [
        'Quais áreas possuem maior risco?',
        'Quantas pessoas vivem nas áreas de risco alto ou crítico?',
      ] },
      { titulo: 'Ocorrências', perguntas: [
        'Quais ocorrências estão abertas?',
        'Qual é a ocorrência mais prioritária agora?',
      ] },
    ],
    cidadao: [
      { titulo: 'Hoje na cidade', perguntas: [
        'A situação da cidade está normal?',
        'Vai chover forte hoje?',
        'Existe algum alerta ativo?',
      ] },
      { titulo: 'Perto de mim', usaBairro: true, perguntas: [
        'Meu bairro corre risco de alagamento?',
        'Tem canal ou córrego com nível alto perto de mim?',
        'Tem bueiro entupido na minha região?',
      ] },
      { titulo: 'O que fazer', perguntas: [
        'O que devo fazer se a rua começar a alagar?',
        'Como me proteger durante uma enchente?',
        'Para quem ligar em caso de emergência?',
      ] },
    ],
  };

  // Nomes amigáveis das tools do MCP (para os selos "consultando...")
  const NOMES_DAS_TOOLS = {
    consultar_situacao_cidade: 'Situação geral da cidade',
    analisar_risco: 'Análise de risco',
    consultar_previsao_chuva: 'Previsão de chuva',
    consultar_sensores: 'Sensores',
    consultar_sensor: 'Detalhe do sensor',
    historico_sensor: 'Histórico do sensor',
    consultar_canais: 'Canais',
    analisar_fluxo_canal: 'Fluxo do canal',
    consultar_bueiros: 'Bueiros',
    consultar_barragens: 'Barragens',
    consultar_areas_risco: 'Áreas de risco',
    consultar_alertas: 'Alertas',
    consultar_ocorrencias: 'Ocorrências',
  };

  const estado = {
    perfil: 'cidadao',
    sessaoId: null,
    enviando: false,
    abortador: null,
    categoria: 0,
    painelAberto: true,
    temMensagens: false,
  };

  const $ = (id) => document.getElementById(id);

  function escapar(texto) {
    return String(texto ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  }

  function guardado(chave, valor) {
    try {
      if (valor === undefined) return sessionStorage.getItem(chave);
      if (valor === null) sessionStorage.removeItem(chave);
      else sessionStorage.setItem(chave, valor);
    } catch (e) { /* armazenamento bloqueado: segue sem ele */ }
    return null;
  }

  // ===================================================================
  // TEXTO DA RESPOSTA: markdown simples e seguro (tudo é escapado antes)
  // ===================================================================
  function emLinha(texto) {
    return escapar(texto)
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
      .replace(/`([^`]+)`/g, '<code class="px-1 rounded bg-white/10 text-petrol-300">$1</code>');
  }

  function renderizarTexto(texto) {
    let html = '';
    let lista = null;
    const fechaLista = () => { if (lista) { html += `</${lista}>`; lista = null; } };
    texto.split('\n').forEach((linha) => {
      const item = linha.match(/^\s*([-*•]|\d+[.)])\s+(.*)$/);
      if (item) {
        const tipo = /\d/.test(item[1]) ? 'ol' : 'ul';
        if (lista !== tipo) {
          fechaLista();
          lista = tipo;
          html += `<${tipo} class="${tipo === 'ol' ? 'list-decimal' : 'list-disc'} pl-5 space-y-1">`;
        }
        html += `<li>${emLinha(item[2])}</li>`;
        return;
      }
      fechaLista();
      if (linha.trim()) html += `<p>${emLinha(linha.replace(/^#+\s*/, ''))}</p>`;
    });
    fechaLista();
    return html;
  }

  // ===================================================================
  // INTERFACE
  // ===================================================================
  function montarInterface() {
    if ($('assistentePainel')) return;
    const painel = document.createElement('div');
    painel.id = 'assistentePainel';
    painel.className = 'hidden fixed inset-0 z-40 sm:inset-auto sm:right-4 sm:top-24 sm:bottom-4 sm:w-[430px]';
    painel.setAttribute('role', 'dialog');
    painel.setAttribute('aria-label', 'Assistente de inteligência artificial');
    painel.innerHTML = `
      <div class="glass-shell h-full flex flex-col overflow-hidden sm:rounded-[28px]">
        <div class="flex items-start justify-between gap-3 px-4 sm:px-5 pt-4 pb-3 border-b border-white/10">
          <div class="min-w-0">
            <span class="text-[11px] font-semibold uppercase tracking-wider text-petrol-300 block">Assistente IA • Claude</span>
            <h2 id="assTitulo" class="text-base sm:text-lg font-semibold text-white leading-tight">Tire suas dúvidas</h2>
            <p id="assSubtitulo" class="text-[11px] text-slate-400 mt-0.5">Responde usando os dados reais do sistema (MCP).</p>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <button type="button" id="assNova" title="Nova conversa" aria-label="Nova conversa"
              class="h-9 px-3 rounded-full bg-white/5 hover:bg-white/10 text-[11px] font-medium text-slate-200 transition">Nova</button>
            <button type="button" id="assFechar" title="Fechar" aria-label="Fechar o assistente"
              class="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white flex items-center justify-center text-sm transition">✕</button>
          </div>
        </div>

        <div id="assAviso" class="hidden mx-4 sm:mx-5 mt-3 px-3.5 py-2.5 rounded-2xl bg-signal-amber/10 border border-signal-amber/40 text-xs text-signal-amber leading-relaxed"></div>

        <div id="assMensagens" role="log" aria-live="polite" class="flex-1 overflow-y-auto overscroll-contain px-4 sm:px-5 py-4 space-y-3"></div>

        <div id="assPainelPerguntas" class="border-t border-white/10 bg-abyss-950/60 px-4 sm:px-5 pt-3 pb-2 max-h-[46%] overflow-y-auto"></div>

        <form id="assForm" class="px-4 sm:px-5 pt-2 pb-4 border-t border-white/10" style="padding-bottom: max(1rem, env(safe-area-inset-bottom))">
          <div class="flex items-end gap-2">
            <button type="button" id="assAlternarPainel" aria-expanded="true" aria-controls="assPainelPerguntas" title="Painel de perguntas"
              class="h-11 px-3.5 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] font-medium text-petrol-300 transition shrink-0">Perguntas</button>
            <label for="assEntrada" class="sr-only">Escreva sua pergunta</label>
            <textarea id="assEntrada" rows="1" maxlength="2000" placeholder="Escreva sua pergunta..."
              class="flex-1 min-w-0 max-h-32 resize-none px-3.5 py-2.5 rounded-2xl bg-abyss-950/85 border border-white/10 focus:border-petrol-300/60 focus:outline-none text-sm text-white placeholder:text-slate-500"></textarea>
            <button type="submit" id="assEnviar" aria-label="Enviar"
              class="h-11 w-11 rounded-2xl bg-petrol-300 hover:brightness-110 text-abyss-950 font-bold flex items-center justify-center transition shrink-0 disabled:opacity-40 disabled:cursor-not-allowed">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14m-6-6l6 6-6 6"/></svg>
            </button>
          </div>
          <p class="text-[10px] text-slate-500 mt-2 leading-snug">A IA pode errar. Em emergência, ligue 193 (Bombeiros) ou 199 (Defesa Civil).</p>
        </form>
      </div>`;
    document.body.appendChild(painel);

    $('assFechar').addEventListener('click', fechar);
    $('assNova').addEventListener('click', novaConversa);
    $('assAlternarPainel').addEventListener('click', () => definirPainelAberto(!estado.painelAberto));
    $('assForm').addEventListener('submit', (e) => { e.preventDefault(); enviarDaEntrada(); });
    const entrada = $('assEntrada');
    entrada.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); enviarDaEntrada(); }
    });
    entrada.addEventListener('input', () => {
      entrada.style.height = 'auto';
      entrada.style.height = `${Math.min(entrada.scrollHeight, 128)}px`;
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !painel.classList.contains('hidden') && $('mcpInspectorDrawer')?.classList.contains('hidden') !== false) fechar();
    });
  }

  // ---------------------------------------------------------------- painel de perguntas

  function definirPainelAberto(aberto) {
    estado.painelAberto = aberto;
    $('assPainelPerguntas').classList.toggle('hidden', !aberto);
    $('assAlternarPainel').setAttribute('aria-expanded', String(aberto));
    if (aberto) desenharPainelDePerguntas();
  }

  function desenharPainelDePerguntas() {
    const categorias = PERGUNTAS[estado.perfil];
    if (estado.categoria >= categorias.length) estado.categoria = 0;
    const atual = categorias[estado.categoria];

    const abas = categorias.map((cat, i) => `
      <button type="button" data-categoria="${i}" aria-pressed="${i === estado.categoria}"
        class="whitespace-nowrap px-3 py-1.5 rounded-full text-[11px] font-medium border transition ${
          i === estado.categoria
            ? 'bg-petrol-300 text-abyss-950 border-petrol-300'
            : 'bg-white/5 text-slate-300 border-white/10 hover:text-white hover:bg-white/10'
        }">${escapar(cat.titulo)}</button>`).join('');

    const campoBairro = atual.usaBairro ? `
      <label class="block mb-2.5">
        <span class="text-[11px] text-slate-400 block mb-1">Seu bairro ou região (opcional, ajuda a IA a responder)</span>
        <input id="assBairro" type="text" maxlength="60" value="${escapar(guardado('assistente_bairro') || '')}" placeholder="Ex.: Setor Central"
          class="w-full px-3 py-2 rounded-xl bg-abyss-950/85 border border-white/10 focus:border-petrol-300/60 focus:outline-none text-xs text-white placeholder:text-slate-500" />
      </label>` : '';

    const perguntas = atual.perguntas.map((p, i) => `
      <button type="button" data-pergunta="${i}" ${estado.enviando ? 'disabled' : ''}
        class="w-full text-left px-3.5 py-2.5 rounded-2xl bg-abyss-950/70 hover:bg-abyss-900 border border-white/10 hover:border-petrol-300/40 text-xs sm:text-[13px] text-slate-200 hover:text-white transition disabled:opacity-50 disabled:cursor-not-allowed">${escapar(p)}</button>`).join('');

    $('assPainelPerguntas').innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-300">Painel de perguntas</span>
        <span class="text-[10px] text-slate-500">Toque em uma pergunta</span>
      </div>
      <div class="flex gap-1.5 overflow-x-auto pb-2 -mx-1 px-1" role="group" aria-label="Assuntos">${abas}</div>
      ${campoBairro}
      <div class="space-y-1.5 pb-1">${perguntas}</div>`;

    $('assPainelPerguntas').querySelectorAll('[data-categoria]').forEach((botao) =>
      botao.addEventListener('click', () => { estado.categoria = Number(botao.dataset.categoria); desenharPainelDePerguntas(); }));
    $('assPainelPerguntas').querySelectorAll('[data-pergunta]').forEach((botao) =>
      botao.addEventListener('click', () => {
        let texto = atual.perguntas[Number(botao.dataset.pergunta)];
        const campo = $('assBairro');
        if (campo) {
          const bairro = campo.value.trim();
          guardado('assistente_bairro', bairro || null);
          if (bairro) texto = `Moro em ${bairro}. ${texto}`;
        }
        enviar(texto);
      }));
  }

  function boasVindas() {
    const operador = estado.perfil === 'defesa_civil';
    $('assTitulo').textContent = operador ? 'Assistente do Centro de Comando' : 'Tire suas dúvidas';
    $('assSubtitulo').textContent = operador
      ? 'Análises e consultas com os dados reais do sistema (MCP).'
      : 'Respondo sobre chuva e alagamentos usando os dados da cidade.';
    $('assMensagens').innerHTML = `
      <div class="rounded-2xl bg-petrol-700/15 border border-petrol-300/25 px-4 py-3.5 text-sm text-slate-100 leading-relaxed space-y-1.5">
        <p class="font-semibold text-white">${operador ? 'Olá! Sobre o que você quer saber?' : 'Olá! Como posso ajudar?'}</p>
        <p class="text-xs text-slate-300">${operador
          ? 'Escolha uma pergunta no painel abaixo ou escreva a sua. Eu consulto sensores, canais, bueiros, barragens, alertas e ocorrências em tempo real.'
          : 'Escolha uma pergunta no painel abaixo ou escreva a sua. Eu olho os dados da cidade e explico de forma simples.'}</p>
      </div>`;
    estado.temMensagens = false;
  }

  // ---------------------------------------------------------------- mensagens

  function rolarParaOFim(forcar) {
    const el = $('assMensagens');
    const perto = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (forcar || perto) el.scrollTop = el.scrollHeight;
  }

  function adicionarMensagemDoUsuario(texto) {
    if (!estado.temMensagens) { $('assMensagens').innerHTML = ''; estado.temMensagens = true; }
    const el = document.createElement('div');
    el.className = 'flex justify-end';
    el.innerHTML = '<div class="max-w-[85%] px-3.5 py-2.5 rounded-2xl rounded-br-md bg-petrol-300 text-abyss-950 text-sm font-medium whitespace-pre-wrap break-words"></div>';
    el.firstChild.textContent = texto;
    $('assMensagens').appendChild(el);
    rolarParaOFim(true);
  }

  function criarMensagemDoAssistente() {
    const el = document.createElement('div');
    el.className = 'flex justify-start';
    el.innerHTML = `
      <div class="max-w-[92%] min-w-0 space-y-2">
        <div data-tools class="flex flex-wrap gap-1.5"></div>
        <div data-corpo class="px-3.5 py-2.5 rounded-2xl rounded-bl-md bg-abyss-950/75 border border-white/10 text-sm text-slate-100 leading-relaxed space-y-2 break-words">
          <span data-status class="text-xs text-slate-400 animate-pulse">Pensando...</span>
        </div>
      </div>`;
    $('assMensagens').appendChild(el);
    rolarParaOFim(true);
    return { corpo: el.querySelector('[data-corpo]'), tools: el.querySelector('[data-tools]'), texto: '', chips: {} };
  }

  function seloDaTool(msg, evento, estadoDoSelo, ms) {
    const nome = NOMES_DAS_TOOLS[evento.nome] || evento.nome;
    let selo = msg.chips[evento.id];
    if (!selo) {
      selo = document.createElement('span');
      selo.title = estado.perfil === 'defesa_civil' ? `Ferramenta MCP: ${evento.nome}` : '';
      msg.tools.appendChild(selo);
      msg.chips[evento.id] = selo;
    }
    const estilos = {
      rodando: ['bg-signal-amber/10 border-signal-amber/40 text-signal-amber animate-pulse', `Consultando: ${nome}`],
      ok: ['bg-petrol-300/10 border-petrol-300/35 text-petrol-300', `✓ ${nome}${ms ? ` · ${(ms / 1000).toFixed(1).replace('.', ',')} s` : ''}`],
      erro: ['bg-signal-coral/10 border-signal-coral/40 text-signal-coral', `${nome}: indisponível`],
    };
    selo.className = `px-2.5 py-1 rounded-full border text-[11px] font-medium ${estilos[estadoDoSelo][0]}`;
    selo.textContent = estilos[estadoDoSelo][1];
  }

  function atualizarTexto(msg) {
    msg.corpo.innerHTML = msg.texto ? renderizarTexto(msg.texto) : msg.corpo.innerHTML;
    rolarParaOFim(false);
  }

  function mostrarErroNaMensagem(msg, texto) {
    const aviso = document.createElement('p');
    aviso.className = 'text-xs text-signal-coral font-medium';
    aviso.textContent = texto;
    msg.corpo.querySelector('[data-status]')?.remove();
    msg.corpo.appendChild(aviso);
    rolarParaOFim(true);
  }

  // ---------------------------------------------------------------- envio e resposta (SSE)

  function definirEnviando(enviando) {
    estado.enviando = enviando;
    const botao = $('assEnviar');
    botao.disabled = false;
    botao.type = enviando ? 'button' : 'submit';
    botao.setAttribute('aria-label', enviando ? 'Parar' : 'Enviar');
    botao.innerHTML = enviando
      ? '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>'
      : '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14m-6-6l6 6-6 6"/></svg>';
    botao.onclick = enviando ? () => estado.abortador?.abort() : null;
    $('assMensagens').setAttribute('aria-busy', String(enviando));
    $('assPainelPerguntas').querySelectorAll('[data-pergunta]').forEach((b) => { b.disabled = enviando; });
  }

  function enviarDaEntrada() {
    const entrada = $('assEntrada');
    const texto = entrada.value.trim();
    if (!texto || estado.enviando) return;
    entrada.value = '';
    entrada.style.height = 'auto';
    enviar(texto);
  }

  async function enviar(texto) {
    if (estado.enviando) return;
    adicionarMensagemDoUsuario(texto);
    // Com a conversa em andamento, o painel de perguntas recolhe para dar espaço às respostas.
    definirPainelAberto(false);
    const msg = criarMensagemDoAssistente();
    estado.abortador = new AbortController();
    definirEnviando(true);

    try {
      const resposta = await fetch(`${ASSISTENTE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mensagem: texto, sessaoId: estado.sessaoId, perfil: estado.perfil }),
        signal: estado.abortador.signal,
      });
      if (!resposta.ok) {
        let detalhe = '';
        try { detalhe = (await resposta.json()).erro; } catch (e) { /* sem corpo */ }
        throw new Error(detalhe || `O assistente respondeu com erro ${resposta.status}.`);
      }
      await lerFluxo(resposta, msg);
    } catch (erro) {
      if (erro.name === 'AbortError') {
        mostrarErroNaMensagem(msg, 'Resposta interrompida.');
      } else if (erro instanceof TypeError) {
        mostrarErroNaMensagem(msg, `Não foi possível falar com o assistente (${ASSISTENTE_URL}). Ele está rodando? Abra o iniciar_assistente.bat.`);
        verificarEstado();
      } else {
        mostrarErroNaMensagem(msg, erro.message);
      }
    } finally {
      msg.corpo.querySelector('[data-status]')?.remove();
      Object.values(msg.chips).forEach((selo) => { if (selo.className.includes('animate-pulse')) selo.remove(); });
      definirEnviando(false);
      estado.abortador = null;
    }
  }

  async function lerFluxo(resposta, msg) {
    const leitor = resposta.body.getReader();
    const decodificador = new TextDecoder();
    let pendente = '';
    for (;;) {
      const { value, done } = await leitor.read();
      if (done) break;
      pendente += decodificador.decode(value, { stream: true });
      let corte;
      while ((corte = pendente.indexOf('\n\n')) !== -1) {
        const bloco = pendente.slice(0, corte);
        pendente = pendente.slice(corte + 2);
        if (bloco.startsWith('data: ')) tratarEvento(JSON.parse(bloco.slice(6)), msg);
      }
    }
  }

  function tratarEvento(evento, msg) {
    switch (evento.type) {
      case 'inicio':
        estado.sessaoId = evento.sessaoId;
        break;
      case 'pensando':
        break;
      case 'texto':
        msg.corpo.querySelector('[data-status]')?.remove();
        msg.texto += evento.texto;
        atualizarTexto(msg);
        break;
      case 'tool':
        seloDaTool(msg, evento, 'rodando');
        break;
      case 'tool_fim':
        seloDaTool(msg, evento, evento.ok ? 'ok' : 'erro', evento.ms);
        break;
      case 'erro':
        mostrarErroNaMensagem(msg, evento.mensagem);
        break;
      default:
        break;
    }
  }

  // ---------------------------------------------------------------- abrir, fechar, estado

  async function verificarEstado() {
    const aviso = $('assAviso');
    try {
      const controle = new AbortController();
      const timer = setTimeout(() => controle.abort(), 5000);
      const resposta = await fetch(`${ASSISTENTE_URL}/`, { signal: controle.signal });
      clearTimeout(timer);
      const dados = await resposta.json();
      let texto = '';
      if (!dados.chaveConfigurada) texto = 'Falta a chave da API da Anthropic. Preencha ANTHROPIC_API_KEY no arquivo assistente/.env e reinicie o assistente.';
      else if (!dados.mcp.acessivel) texto = 'O assistente não está conseguindo falar com o MCP Server. Confira se o MCP está rodando (porta 8000).';
      aviso.textContent = texto;
      aviso.classList.toggle('hidden', !texto);
    } catch (e) {
      aviso.textContent = 'O assistente está desligado. Abra o iniciar_assistente.bat (ou o iniciar_projeto.bat) e tente de novo.';
      aviso.classList.remove('hidden');
    }
  }

  function novaConversa() {
    estado.abortador?.abort();
    estado.sessaoId = null;
    boasVindas();
    definirPainelAberto(true);
  }

  function abrir() {
    montarInterface();
    $('assistentePainel').classList.remove('hidden');
    if (!estado.temMensagens) { boasVindas(); definirPainelAberto(true); }
    verificarEstado();
    if (!window.matchMedia('(pointer: coarse)').matches) $('assEntrada').focus();
  }

  function fechar() {
    $('assistentePainel')?.classList.add('hidden');
  }

  function alternar() {
    const painel = $('assistentePainel');
    if (painel && !painel.classList.contains('hidden')) fechar(); else abrir();
  }

  /** Chamado quando o perfil muda (entrar, trocar de perfil): cada perfil tem a sua conversa. */
  function sincronizarPerfil() {
    const novo = typeof appState !== 'undefined' && appState.role === 'civil' ? 'defesa_civil' : 'cidadao';
    if (novo === estado.perfil) return;
    estado.perfil = novo;
    estado.categoria = 0;
    estado.sessaoId = null;
    estado.temMensagens = false;
    fechar();
  }

  window.Assistente = { abrir, fechar, alternar, sincronizarPerfil, perguntar: enviar };

  document.addEventListener('DOMContentLoaded', () => {
    montarInterface();
    ['assistenteBtn', 'assistenteBtnMobile'].forEach((id) => $(id)?.addEventListener('click', alternar));
  });
})();
