async function carregarCockpit() {
  document.getElementById('data-hora').textContent =
    new Date().toLocaleString('pt-BR', { dateStyle: 'full', timeStyle: 'short' });

  try {
    const [resumo, ibov, cambio, macro] = await Promise.all([
      fetch('/carteira/resumo').then(r => r.json()),
      fetch('/mercado/ibovespa').then(r => r.json()),
      fetch('/mercado/cambio').then(r => r.json()),
      fetch('/macro/regime').then(r => r.json())
    ]);

    // ── KPIs ─────────────────────────────────────────────
    document.getElementById('kpi-patrimonio').textContent = fmtMoeda(resumo.patrimonio_total);
    document.getElementById('kpi-investido').textContent = fmtMoeda(resumo.total_investido);
    document.getElementById('kpi-cambio').textContent = 'R$ ' + fmt(resumo.cambio_usd_brl);

    const res = resumo.retorno_total_rs;
    const resPct = resumo.retorno_total_pct;
    document.getElementById('kpi-resultado').textContent = fmtMoeda(res);
    const sub = document.getElementById('kpi-resultado-pct');
    sub.textContent = (resPct >= 0 ? '▲ +' : '▼ ') + fmt(resPct) + '%';
    sub.className = 'card-sub ' + (resPct >= 0 ? 'pos' : 'neg');

    const retSub = document.getElementById('kpi-retorno');
    retSub.textContent = (resPct >= 0 ? '▲ +' : '▼ ') + fmt(resPct) + '% total';
    retSub.className = 'card-sub ' + (resPct >= 0 ? 'pos' : 'neg');

    // ── REGIME MACRO ──────────────────────────────────────
    const regimeCor = { 'DEFENSIVO': '#8B1A1A', 'NEUTRO': '#C8860A', 'AGRESSIVO': '#1E6E3A' };
    const regimeEl = document.getElementById('regime-macro');
    if (regimeEl) {
      const cor = regimeCor[macro.regime] || '#888';
      regimeEl.innerHTML = `
        <div class="card-label">Regime Macro</div>
        <div style="font-size:22px;font-weight:700;color:${cor};">${macro.regime}</div>
        <div class="card-sub">Selic ${macro.detalhes.selic_atual}% · Juro real ${macro.detalhes.juro_real}%</div>
      `;
    }

    // ── ALOCAÇÃO ──────────────────────────────────────────
    const aloc = document.getElementById('alocacao-lista');
    const total = resumo.patrimonio_total;
    let html = '';
    const cores = {
      ACAO: '#1A1814', FII: '#C8860A', ETF_BR: '#1A5C8A',
      ETF_EUA: '#1E6E3A', TESOURO: '#6B4F1E', RF: '#888'
    };
    for (const [classe, valor] of Object.entries(resumo.por_classe)) {
      const pct = total > 0 ? (valor / total * 100) : 0;
      const cor = cores[classe] || '#888';
      html += `<div style="margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;">
          <span style="font-weight:600;">${classe}</span>
          <span>${fmtMoeda(valor)} · <strong>${fmt(pct)}%</strong></span>
        </div>
        <div style="background:#F0EDE6;border-radius:3px;height:6px;overflow:hidden;">
          <div style="width:${pct}%;height:100%;background:${cor};border-radius:3px;transition:width 0.5s;"></div>
        </div>
      </div>`;
    }
    aloc.innerHTML = html || '<div class="loading">Nenhum ativo cadastrado</div>';

    // ── IBOVESPA ──────────────────────────────────────────
    const ibovEl = document.getElementById('ibov-info');
    const ibovVar = ibov.variacao_dia || 0;
    ibovEl.innerHTML = `
      <div style="font-size:28px;font-weight:700;letter-spacing:-0.02em;">${fmt(ibov.preco, 0)}</div>
      <div class="card-sub ${ibovVar >= 0 ? 'pos' : 'neg'}">${ibovVar >= 0 ? '▲ +' : '▼ '}${fmt(ibovVar)}% hoje</div>
      <div class="card-sub" style="margin-top:8px;">Câmbio: R$ ${fmt(resumo.cambio_usd_brl)}</div>
    `;

    // ── TOP ATIVOS DA CARTEIRA ────────────────────────────
    await carregarTopAtivos();

  } catch(e) {
    console.error('Erro no cockpit:', e);
  }
}

async function carregarTopAtivos() {
  const el = document.getElementById('top-ativos');
  if (!el) return;

  try {
    const ativos = await fetch('/ativos').then(r => r.json());

    if (!ativos.length) {
      el.innerHTML = '<div class="loading">Nenhum ativo cadastrado.</div>';
      return;
    }

    // Ordena por retorno
    const ordenados = [...ativos].sort((a, b) => b.retorno_pct - a.retorno_pct);

    let html = '';
    ordenados.slice(0, 5).forEach(a => {
      const retCls = a.retorno_pct >= 0 ? 'pos' : 'neg';
      const retSinal = a.retorno_pct >= 0 ? '+' : '';
      const varCls = a.variacao_dia >= 0 ? 'pos' : 'neg';
      const varSinal = a.variacao_dia >= 0 ? '+' : '';

      html += `
        <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #F0EDE6;">
          <div style="flex:1;">
            <div style="font-weight:700;font-size:13px;">${a.ticker}</div>
            <div style="font-size:10px;color:#888;">${a.nome || a.classe}</div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:13px;font-weight:600;">${fmtMoeda(a.preco_atual)}</div>
            <div style="font-size:10px;color:#888;">${varSinal}${fmt(a.variacao_dia)}% hoje</div>
          </div>
          <div style="text-align:right;min-width:70px;">
            <span class="pill ${a.retorno_pct >= 0 ? 'p-green' : 'p-red'}">${retSinal}${fmt(a.retorno_pct)}%</span>
            <div style="font-size:10px;color:#888;margin-top:3px;">${fmtMoeda(a.valor_atual)}</div>
          </div>
        </div>`;
    });

    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<div class="loading">Erro ao carregar ativos.</div>';
  }
}

function fmt(v, decimais = 2) {
  if (v === null || v === undefined) return '—';
  return v.toLocaleString('pt-BR', { minimumFractionDigits: decimais, maximumFractionDigits: decimais });
}

function fmtMoeda(v) {
  if (v === null || v === undefined) return '—';
  return 'R$ ' + fmt(v);
}

function carregarTudo() { carregarCockpit(); }
