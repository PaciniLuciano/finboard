async function carregarDividendos() {
  const tbody = document.getElementById('tabela-dividendos');
  const resumo = document.getElementById('resumo-dividendos');

  try {
    const [divs, ativos] = await Promise.all([
      fetch('/dividendos').then(r => r.json()),
      fetch('/ativos').then(r => r.json())
    ]);

    // Resumo total
    const totalRecebido = divs.reduce((sum, d) => sum + d.valor_total, 0);
    const mesAtual = new Date().toISOString().slice(0, 7);
    const totalMes = divs.filter(d => d.data_pagamento.startsWith(mesAtual))
                        .reduce((sum, d) => sum + d.valor_total, 0);

    resumo.innerHTML = `
      <div class="grid-4" style="margin-bottom:20px;">
        <div class="card">
          <div class="card-label">Total Recebido</div>
          <div class="card-value green">${fmtMoeda(totalRecebido)}</div>
          <div class="card-sub">${divs.length} proventos registrados</div>
        </div>
        <div class="card">
          <div class="card-label">Recebido este mês</div>
          <div class="card-value">${fmtMoeda(totalMes)}</div>
          <div class="card-sub pos">mês atual</div>
        </div>
        <div class="card">
          <div class="card-label">Média Mensal</div>
          <div class="card-value">${fmtMoeda(divs.length > 0 ? totalRecebido / 12 : 0)}</div>
          <div class="card-sub">estimativa anualizada</div>
        </div>
        <div class="card">
          <div class="card-label">Ativos com Proventos</div>
          <div class="card-value">${new Set(divs.map(d => d.ticker)).size}</div>
          <div class="card-sub">tickers distintos</div>
        </div>
      </div>
    `;

    if (!divs.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="loading">Nenhum provento registrado.</td></tr>';
      return;
    }

    tbody.innerHTML = divs.map(d => `<tr>
      <td><span style="font-weight:700;">${d.ticker}</span></td>
      <td><span class="pill p-blue">${d.tipo}</span></td>
      <td>${fmtMoeda(d.valor_por_cota)}/cota</td>
      <td>${fmt(d.quantidade_cotas, 0)} cotas</td>
      <td style="font-weight:700;color:#1E6E3A;">${fmtMoeda(d.valor_total)}</td>
      <td>${new Date(d.data_pagamento).toLocaleDateString('pt-BR')}</td>
    </tr>`).join('');

  } catch(e) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading">Erro ao carregar.</td></tr>';
  }
}

async function carregarRetornoTotal() {
  const el = document.getElementById('retorno-total-lista');
  el.innerHTML = '<div class="loading">Calculando retorno total...</div>';

  try {
    const ativos = await fetch('/ativos').then(r => r.json());
    const fiis = ativos.filter(a => a.classe === 'FII');

    if (!fiis.length) {
      el.innerHTML = '<div class="loading">Nenhum FII na carteira.</div>';
      return;
    }

    const resultados = await Promise.all(
      fiis.map(a => fetch(`/retorno-total/${a.ticker}`).then(r => r.json()))
    );

    let html = `
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Ativo</th>
            <th>Valoriz. Cota</th>
            <th>Dividendos Recebidos</th>
            <th>DY s/ PM</th>
            <th>Retorno Total</th>
            <th>Proventos</th>
          </tr></thead>
          <tbody>
    `;

    resultados.forEach(r => {
      const totCls = r.retorno_total_pct >= 0 ? 'p-green' : 'p-red';
      const cotaCls = r.retorno_cota_pct >= 0 ? 'pos' : 'neg';
      html += `<tr>
        <td><span style="font-weight:700;">${r.ticker}</span></td>
        <td>
          <div class="${cotaCls}" style="font-weight:600;">${r.retorno_cota_pct >= 0 ? '+' : ''}${fmt(r.retorno_cota_pct)}%</div>
          <div style="font-size:10px;color:#888;">${fmtMoeda(r.retorno_cota_rs)}</div>
        </td>
        <td style="color:#1E6E3A;font-weight:600;">${fmtMoeda(r.total_dividendos)}</td>
        <td style="color:#1E6E3A;font-weight:600;">+${fmt(r.dy_recebido_pct)}%</td>
        <td><span class="pill ${totCls}" style="font-size:13px;padding:4px 10px;">+${fmt(r.retorno_total_pct)}%</span>
          <div style="font-size:10px;color:#888;margin-top:3px;">${fmtMoeda(r.retorno_total_rs)}</div>
        </td>
        <td style="color:#888;">${r.qtd_proventos} registros</td>
      </tr>`;
    });

    html += '</tbody></table></div>';
    el.innerHTML = html;

  } catch(e) {
    el.innerHTML = '<div class="loading">Erro ao calcular retorno total.</div>';
  }
}

async function registrarDividendo() {
  const msg = document.getElementById('msg-dividendo');
  const ticker = document.getElementById('div-ticker').value.trim().toUpperCase();
  const valor_por_cota = parseFloat(document.getElementById('div-valor-cota').value);
  const quantidade_cotas = parseFloat(document.getElementById('div-quantidade').value);
  const data_pagamento = document.getElementById('div-data').value;
  const tipo = document.getElementById('div-tipo').value;

  if (!ticker || !valor_por_cota || !quantidade_cotas || !data_pagamento) {
    msg.innerHTML = '<div class="alert alert-red">Preencha todos os campos.</div>';
    return;
  }

  try {
    const res = await fetch('/dividendos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, valor_por_cota, quantidade_cotas, data_pagamento, tipo })
    });
    const data = await res.json();
    if (res.ok) {
      msg.innerHTML = `<div class="alert alert-green">✓ ${data.mensagem} · Total: ${fmtMoeda(data.valor_total)}</div>`;
      document.getElementById('div-ticker').value = '';
      document.getElementById('div-valor-cota').value = '';
      document.getElementById('div-quantidade').value = '';
      document.getElementById('div-data').value = '';
      carregarDividendos();
      carregarRetornoTotal();
    } else {
      msg.innerHTML = `<div class="alert alert-red">✗ ${data.detail}</div>`;
    }
  } catch(e) {
    msg.innerHTML = '<div class="alert alert-red">Erro ao registrar.</div>';
  }
}

async function importarTodos() {
  const msg = document.getElementById('msg-dividendo');
  msg.innerHTML = '<div class="alert alert-green">⏳ Importando proventos de todos os ativos...</div>';

  try {
    const res = await fetch('/dividendos/importar-todos', { method: 'POST' });
    const data = await res.json();

    if (data.resultados && data.resultados.length > 0) {
      const detalhes = data.resultados.map(r => `${r.ticker}: ${r.importados} proventos`).join(' · ');
      msg.innerHTML = `<div class="alert alert-green">✓ Importação concluída — ${detalhes}</div>`;
    } else {
      msg.innerHTML = '<div class="alert alert-green">✓ Nenhum provento novo encontrado. Tudo já estava atualizado.</div>';
    }

    carregarDividendos();
    carregarRetornoTotal();
  } catch(e) {
    msg.innerHTML = '<div class="alert alert-red">Erro na importação.</div>';
  }
}

async function importarTicker() {
  const ticker = document.getElementById('import-ticker').value.trim();
  const msg = document.getElementById('msg-dividendo');

  if (!ticker) {
    msg.innerHTML = '<div class="alert alert-red">Digite um ticker.</div>';
    return;
  }

  msg.innerHTML = `<div class="alert alert-green">⏳ Importando proventos de ${ticker}...</div>`;

  try {
    const res = await fetch(`/dividendos/importar/${ticker}`, { method: 'POST' });
    const data = await res.json();

    if (res.ok) {
      msg.innerHTML = `<div class="alert alert-green">✓ ${data.mensagem}</div>`;
      document.getElementById('import-ticker').value = '';
      carregarDividendos();
      carregarRetornoTotal();
    } else {
      msg.innerHTML = `<div class="alert alert-red">✗ ${data.detail}</div>`;
    }
  } catch(e) {
    msg.innerHTML = '<div class="alert alert-red">Erro na importação.</div>';
  }
}
