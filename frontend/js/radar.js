let radarFonte = 'carteira';

async function carregarRadar() {
  const content = document.getElementById('radar-content');
  content.innerHTML = '<div class="loading">⏳ Calculando scores — pode levar 30 segundos...</div>';

  try {
    const endpoint = radarFonte === 'watchlist' ? '/radar?origem=watchlist' : '/radar?origem=carteira';
    const data = await fetch(endpoint + '&forcar=true').then(r => r.json());

    const regimeCor = {
      'DEFENSIVO': '#8B1A1A',
      'NEUTRO': '#C8860A',
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
      html += '<div class="loading">Nenhum ativo para analisar. Adicione ativos à watchlist.</div>';
      content.innerHTML = html;
      return;
    }

    html += `
      <div class="section-title">Ranking por Score — ${radarFonte === 'watchlist' ? 'Watchlist' : 'Minha Carteira'}</div>
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
      const score = a.score_final;
      const scoreCls = score >= 7.5 ? 'p-green' : score >= 5.5 ? 'p-gold' : 'p-red';
      const sinal = score >= 7.5 ? '★ Forte' : score >= 5.5 ? '◎ Neutro' : '▼ Fraco';
      const sinalCls = score >= 7.5 ? 'p-green' : score >= 5.5 ? 'p-gold' : 'p-red';

      html += `<tr>
        <td><div class="ticker">${a.ticker}</div></td>
        <td><span class="pill p-gray">${a.classe}</span></td>
        <td><span class="pill ${a.score_valuation >= 7 ? 'p-green' : a.score_valuation >= 5 ? 'p-gold' : 'p-red'}">${a.score_valuation}</span></td>
        <td><span class="pill ${a.score_momento >= 7 ? 'p-green' : a.score_momento >= 5 ? 'p-gold' : 'p-red'}">${a.score_momento}</span></td>
        <td><span class="pill p-blue">${a.score_macro}</span></td>
        <td><span class="pill ${scoreCls}" style="font-size:13px;padding:4px 10px;">${score}</span></td>
        <td><span class="pill ${sinalCls}">${sinal}</span></td>
      </tr>`;
    });

    html += '</tbody></table></div>';
    content.innerHTML = html;

  } catch(e) {
    content.innerHTML = '<div class="alert alert-red">Erro ao carregar radar.</div>';
  }
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
  const ticker = document.getElementById('wl-ticker').value.trim().toUpperCase();
  const nome = document.getElementById('wl-nome').value.trim();
  const classe = document.getElementById('wl-classe').value;
  const mercado = document.getElementById('wl-mercado').value;
  const msg = document.getElementById('msg-watchlist');

  if (!ticker) {
    msg.innerHTML = '<div class="alert alert-red">Digite um ticker.</div>';
    return;
  }

  try {
    const res = await fetch('/watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, nome, classe, mercado })
    });
    const data = await res.json();
    if (res.ok) {
      msg.innerHTML = `<div class="alert alert-green">✓ ${data.mensagem}</div>`;
      document.getElementById('wl-ticker').value = '';
      document.getElementById('wl-nome').value = '';
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
  carregarWatchlist();
}

function switchRadarFonte(btn, fonte) {
  radarFonte = fonte;

  // Reseta estilos dos botões
  document.getElementById('tab-carteira').style.background = 'transparent';
  document.getElementById('tab-carteira').style.color = '#888';
  document.getElementById('tab-carteira').style.border = '1px solid #DDD9D0';
  document.getElementById('tab-watchlist').style.background = 'transparent';
  document.getElementById('tab-watchlist').style.color = '#888';
  document.getElementById('tab-watchlist').style.border = '1px solid #DDD9D0';

  // Ativa o botão clicado
  btn.style.background = '#1A1814';
  btn.style.color = 'white';
  btn.style.border = 'none';

  document.getElementById('radar-content').innerHTML =
    '<div class="loading">Clique em Calcular para analisar.</div>';

  if (fonte === 'watchlist') {
    document.getElementById('watchlist-panel').style.display = 'block';
    carregarWatchlist();
  } else {
    document.getElementById('watchlist-panel').style.display = 'none';
  }
}
