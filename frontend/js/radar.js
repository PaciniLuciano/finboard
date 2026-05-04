async function carregarRadar() {
  const content = document.getElementById('radar-content');
  content.innerHTML = '<div class="loading">⏳ Calculando scores — pode levar 30 segundos...</div>';

  try {
    const data = await fetch('/radar').then(r => r.json());

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

      <div class="section-title">Ranking dos seus Ativos por Score</div>
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

    html += `</tbody></table></div>`;
    content.innerHTML = html;

  } catch(e) {
    content.innerHTML = '<div class="alert alert-red">Erro ao carregar radar.</div>';
  }
}
