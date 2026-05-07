let radarFonte = 'carteira';
const _radarCache = { carteira: null, watchlist: null };

// Chamado pelo botão "↺ Recalcular" (forcar=true) e pelo showPanel (forcar=false)
async function carregarRadar(forcar = false) {
  // Se tem cache e não está forçando, renderiza direto
  if (!forcar && _radarCache[radarFonte]) {
    renderRadar(_radarCache[radarFonte]);
    return;
  }

  const content = document.getElementById('radar-content');
  content.innerHTML = '<div class="loading">⏳ Calculando scores — pode levar 30 segundos...</div>';

  try {
    const origem = radarFonte === 'watchlist' ? 'watchlist' : 'carteira';
    const forcarParam = forcar ? '&forcar=true' : '';
    const data = await fetch(`/radar?origem=${origem}${forcarParam}`).then(r => r.json());

    _radarCache[radarFonte] = data;
    renderRadar(data);
  } catch(e) {
    content.innerHTML = '<div class="alert alert-red">Erro ao carregar radar.</div>';
  }
}

function renderRadar(data) {
  const content = document.getElementById('radar-content');

  const regimeCor = {
    'DEFENSIVO': '#8B1A1A',
    'NEUTRO':    '#C8860A',
    'AGRESSIVO': '#1E6E3A'
  };

  let html = `
    <div class="grid-4" style="margin-bottom:20px;">
      <div class="card" style="border-left:4px solid ${regimeCor[data.regime] || '#888'};">
        <div class="card-label">Regime Macro</div>
        <div class="card-value" style="font-size:20px;color:${regimeCor[data.regime]}">${data.regime}</div>
        <div class="card-sub">cenário atual</div>
      </div>
      <div class="card">
        <div class="card-label">Selic</div>
        <div class="card-value" style="font-size:20px;">${data.selic}%</div>
        <div class="card-sub">ao ano</div>
      </div>
      <div class="card">
        <div class="card-label">IPCA 12m</div>
        <div class="card-value" style="font-size:20px;">${data.ipca}%</div>
        <div class="card-sub">inflação</div>
      </div>
      <div class="card">
        <div class="card-label">Juro Real</div>
        <div class="card-value" style="font-size:20px;">${data.juro_real}%</div>
        <div class="card-sub">Selic - IPCA</div>
      </div>
    </div>
  `;

  if (!data.ativos || !data.ativos.length) {
    html += '<div class="loading">Nenhum ativo para analisar.</div>';
    content.innerHTML = html;
    return;
  }

  const fonte = radarFonte === 'watchlist' ? 'Watchlist' : 'Minha Carteira';
  const calc = data.ativos[0]?.calculado_em
    ? ' — calculado em ' + new Date(data.ativos[0].calculado_em).toLocaleTimeString('pt-BR')
    : '';

  html += `
    <div class="section-title">Ranking por Score — ${fonte}${calc}</div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Ativo</th>
          <th>Classe</th>
          <th>Valuation</th>
          <th>Momento</th>
          <th>Macro</th>
          <th>Score Final</th>
          <th>Sinal</th>
        </tr></thead>
        <tbody>
  `;

  data.ativos.forEach(a => {
    const score    = a.score_final;
    const scoreCls = score >= 7.5 ? 'p-green' : score >= 5.5 ? 'p-gold' : 'p-red';
    const sinal    = score >= 7.5 ? '★ Forte'  : score >= 5.5 ? '◎ Neutro' : '▼ Fraco';
    const sinalCls = score >= 7.5 ? 'p-green' : score >= 5.5 ? 'p-gold' : 'p-red';
    const vCls = a.score_valuation >= 7 ? 'p-green' : a.score_valuation >= 5 ? 'p-gold' : 'p-red';
    const mCls = a.score_momento   >= 7 ? 'p-green' : a.score_momento   >= 5 ? 'p-gold' : 'p-red';

    html += `<tr>
      <td><div class="ticker">${a.ticker}</div></td>
      <td><span class="pill p-gray">${a.classe}</span></td>
      <td><span class="pill ${vCls}">${a.score_valuation}</span></td>
      <td><span class="pill ${mCls}">${a.score_momento}</span></td>
      <td><span class="pill p-blue">${a.score_macro}</span></td>
      <td><span class="pill ${scoreCls}" style="font-size:13px;padding:4px 10px;">${score}</span></td>
      <td><span class="pill ${sinalCls}">${sinal}</span></td>
    </tr>`;
  });

  html += '</tbody></table></div>';
  content.innerHTML = html;
}

async function carregarWatchlist() {
  const lista = document.getElementById('watchlist-lista');
  try {
    const itens = await fetch('/watchlist').then(r => r.json());
    if (!itens.length) {
      lista.innerHTML = '<div class="loading">Watchlist vazia. Adicione ativos abaixo.</div>';
      return;
    }
    lista.innerHTML = itens.map(i => `
      <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #F0EDE6;">
        <div style="flex:1;">
          <span style="font-weight:700;font-size:13px;">${i.ticker}</span>
          <span class="pill p-gray" style="margin-left:8px;">${i.classe}</span>
          ${i.nome ? `<span style="font-size:11px;color:#888;margin-left:8px;">${i.nome}</span>` : ''}
        </div>
        <button onclick="removerWatchlist('${i.ticker}')"
          style="padding:3px 8px;font-size:10px;background:#8B1A1A;color:white;border:none;border-radius:4px;cursor:pointer;">✕</button>
      </div>
    `).join('');
  } catch(e) {
    lista.innerHTML = '<div class="loading">Erro ao carregar watchlist.</div>';
  }
}

async function adicionarWatchlist() {
  const ticker  = document.getElementById('wl-ticker').value.trim().toUpperCase();
  const nome    = document.getElementById('wl-nome').value.trim();
  const classe  = document.getElementById('wl-classe').value;
  const mercado = document.getElementById('wl-mercado').value;
  const msg     = document.getElementById('msg-watchlist');

  if (!ticker) { msg.innerHTML = '<div class="alert alert-red">Digite um ticker.</div>'; return; }

  try {
    const res  = await fetch('/watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, nome, classe, mercado })
    });
    const data = await res.json();
    if (res.ok) {
      msg.innerHTML = `<div class="alert alert-green">✓ ${data.mensagem}</div>`;
      document.getElementById('wl-ticker').value = '';
      document.getElementById('wl-nome').value = '';
      _radarCache.watchlist = null; // invalida cache ao mudar watchlist
      carregarWatchlist();
    } else {
      msg.innerHTML = `<div class="alert alert-red">✗ ${data.detail}</div>`;
    }
  } catch(e) {
    msg.innerHTML = '<div class="alert alert-red">Erro ao adicionar.</div>';
  }
}

async function removerWatchlist(ticker) {
  if (!confirm(`Remover ${ticker} da watchlist?`)) return;
  await fetch(`/watchlist/${ticker}`, { method: 'DELETE' });
  _radarCache.watchlist = null; // invalida cache ao mudar watchlist
  carregarWatchlist();
}

function switchRadarFonte(btn, fonte) {
  radarFonte = fonte;

  document.getElementById('tab-carteira').style.cssText = 'padding:8px 18px;background:transparent;color:#888;border:1px solid #DDD9D0;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;';
  document.getElementById('tab-watchlist').style.cssText = 'padding:8px 18px;background:transparent;color:#888;border:1px solid #DDD9D0;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;';
  btn.style.cssText = 'padding:8px 18px;background:#1A1814;color:white;border:none;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;';

  if (fonte === 'watchlist') {
    document.getElementById('watchlist-panel').style.display = 'block';
    carregarWatchlist();
  } else {
    document.getElementById('watchlist-panel').style.display = 'none';
  }

  // Usa cache se disponível, senão mostra prompt
  if (_radarCache[fonte]) {
    renderRadar(_radarCache[fonte]);
  } else {
    document.getElementById('radar-content').innerHTML =
      '<div class="loading">Clique em Calcular para analisar.</div>';
  }
}
