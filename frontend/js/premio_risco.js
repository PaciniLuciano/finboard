let _premioCache = null;

async function carregarPremioRisco(forcar = false) {
  if (!forcar && _premioCache) { renderPremio(_premioCache); return; }

  const content = document.getElementById('premio-content');
  content.innerHTML = '<div class="loading">⏳ Calculando prêmios de risco — pode levar 30 segundos...</div>';

  try {
    const data = await fetch('/premio-risco').then(r => r.json());
    _premioCache = data;
    renderPremio(data);
  } catch(e) {
    content.innerHTML = '<div class="alert alert-red">Erro ao carregar prêmio de risco.</div>';
  }
}

function renderPremio(data) {
  const content = document.getElementById('premio-content');

  const rCor = { ATRATIVO: '#1E6E3A', NEUTRO: '#C8860A', ABAIXO_CDI: '#8B1A1A' };
  const rCls = { ATRATIVO: 'p-green', NEUTRO: 'p-gold', ABAIXO_CDI: 'p-red',
                 SEM_DADO: 'p-gray', 'N/A': 'p-gray', ERRO: 'p-red' };
  const rLabel = { ATRATIVO: '★ Atrativo', NEUTRO: '◎ Neutro',
                   ABAIXO_CDI: '▼ Abaixo CDI', SEM_DADO: '— Sem dado',
                   'N/A': '— N/A', ERRO: '✗ Erro' };

  let html = `
    <div class="grid-4" style="margin-bottom:20px;">
      <div class="card">
        <div class="card-label">CDI aproximado</div>
        <div class="card-value" style="font-size:22px;">${fmt(data.cdi)}%</div>
        <div class="card-sub">Selic ${fmt(data.selic)}% − 0,1%</div>
      </div>
      <div class="card" style="border-left:4px solid #1E6E3A;">
        <div class="card-label">Atrativos</div>
        <div class="card-value" style="font-size:22px;color:#1E6E3A;">${data.resumo.atrativos}</div>
        <div class="card-sub">yield ≥ CDI + alvo</div>
      </div>
      <div class="card" style="border-left:4px solid #C8860A;">
        <div class="card-label">Neutros</div>
        <div class="card-value" style="font-size:22px;color:#C8860A;">${data.resumo.neutros}</div>
        <div class="card-sub">acima CDI, abaixo alvo</div>
      </div>
      <div class="card" style="border-left:4px solid #8B1A1A;">
        <div class="card-label">Abaixo do CDI</div>
        <div class="card-value" style="font-size:22px;color:#8B1A1A;">${data.resumo.abaixo_cdi}</div>
        <div class="card-sub">não remunera o risco</div>
      </div>
    </div>
  `;

  if (!data.ativos || !data.ativos.length) {
    html += '<div class="loading">Nenhum ativo para analisar.</div>';
    content.innerHTML = html;
    return;
  }

  html += `
    <div class="section-title" style="margin-bottom:12px;">Ranking por Prêmio de Risco</div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Ativo</th>
          <th>Classe</th>
          <th>Yield</th>
          <th>Tipo</th>
          <th>CDI + Alvo</th>
          <th>Prêmio/CDI</th>
          <th>Gap</th>
          <th>Sinal</th>
        </tr></thead>
        <tbody>
  `;

  data.ativos.forEach(a => {
    const sinal = a.sinal || 'SEM_DADO';
    const cls   = rCls[sinal] || 'p-gray';
    const label = rLabel[sinal] || sinal;

    const yieldStr = a.yield_esperado != null
      ? `<span class="pill ${a.yield_esperado >= (a.benchmark||0) ? 'p-green' : a.yield_esperado >= (a.cdi||0) ? 'p-gold' : 'p-red'}">${fmt(a.yield_esperado)}%</span>`
      : '<span class="pill p-gray">—</span>';

    const tipoStr = a.yield_tipo
      ? `<span style="font-size:10px;color:#888;">${a.yield_tipo}</span>`
      : '—';

    const benchStr = a.benchmark != null
      ? `${fmt(a.benchmark)}%` + (a.premio_minimo > 0 ? `<br><small style="color:#888;">(+${fmt(a.premio_minimo)}%)</small>` : '')
      : '—';

    const premioCdiStr = a.premio_cdi != null
      ? `<span class="pill ${a.premio_cdi >= 0 ? 'p-green' : 'p-red'}">${a.premio_cdi >= 0 ? '+' : ''}${fmt(a.premio_cdi)}%</span>`
      : '—';

    const gapStr = a.gap != null
      ? `<span style="color:${a.gap >= 0 ? '#1E6E3A' : '#8B1A1A'};font-weight:700;">${a.gap >= 0 ? '+' : ''}${fmt(a.gap)}%</span>`
      : '—';

    const detStr = a.erro
      ? `<small style="color:#c55;font-size:9px;" title="${a.erro}">ver erro ⓘ</small>`
      : a.detalhes?.pe
        ? `<small style="color:#aaa;">P/L ${fmt(a.detalhes.pe)}</small>`
        : a.detalhes?.dy
          ? `<small style="color:#aaa;">DY ${fmt(a.detalhes.dy)}%</small>`
          : '';

    html += `<tr>
      <td><div class="ticker">${a.ticker}</div>${detStr}</td>
      <td><span class="pill p-gray" style="font-size:10px;">${a.classe}</span></td>
      <td>${yieldStr}</td>
      <td>${tipoStr}</td>
      <td style="font-size:12px;">${benchStr}</td>
      <td>${premioCdiStr}</td>
      <td style="font-size:13px;font-weight:700;">${gapStr}</td>
      <td><span class="pill ${cls}">${label}</span></td>
    </tr>`;
  });

  html += `</tbody></table></div>
    <div style="font-size:11px;color:#aaa;margin-top:8px;">
      Yield "lucro" = Earnings Yield (1/P&L × 100). Yield "dividendo" = DY anualizado via yfinance.
      CDI ≈ Selic − 0,1%. Alvo por classe: ACAO +8,5% · FII +3% · ETF_BR +5% · ETF_EUA +8% · RF +0%.
    </div>`;

  content.innerHTML = html;
}
