async function carregarRendaFixa() {
  const tbody = document.getElementById('tabela-rf');
  const resumo = document.getElementById('resumo-rf');
  tbody.innerHTML = '<tr><td colspan="8" class="loading">Carregando...</td></tr>';

  try {
    const [itens, macro] = await Promise.all([
      fetch('/renda-fixa').then(r => r.json()),
      fetch('/macro/regime').then(r => r.json())
    ]);

    const selic = macro.detalhes.selic_atual;
    const cdi = selic - 0.1; // CDI ≈ Selic - 0.1%
    const ipca = macro.detalhes.ipca_12m;

    if (!itens.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="loading">Nenhum título cadastrado.</td></tr>';
      resumo.innerHTML = '';
      return;
    }

    // Calcula totais
    let totalAplicado = 0;
    let totalRendimento = 0;

    const hoje = new Date();

    const rows = itens.map(item => {
      totalAplicado += item.valor_aplicado;

      // Calcula rentabilidade anual estimada
      let rentAnual = 0;
      if (item.indexador === 'CDI') {
        rentAnual = (item.taxa_pct / 100) * cdi;
      } else if (item.indexador === 'IPCA') {
        rentAnual = ipca + item.taxa_pct;
      } else if (item.indexador === 'PREFIXADO') {
        rentAnual = item.taxa_pct;
      }

      // Rendimento mensal estimado
      const rendMensal = item.valor_aplicado * (rentAnual / 100) / 12;
      totalRendimento += rendMensal;

      // Dias para vencimento
      const venc = new Date(item.vencimento);
      const diasParaVenc = Math.ceil((venc - hoje) / (1000 * 60 * 60 * 24));
      const alertaVenc = diasParaVenc < 90;

      // Score simples
      let score = 5.0;
      if (rentAnual > cdi * 1.1) score += 2;
      if (rentAnual > cdi * 1.2) score += 1;
      if (item.fgc) score += 1;
      if (item.liquidez === 'DIARIA') score += 1;
      score = Math.min(score, 10);

      // Formato da taxa
      let taxaStr = '';
      if (item.indexador === 'CDI') {
        taxaStr = `${item.taxa_pct}% CDI`;
      } else if (item.indexador === 'IPCA') {
        taxaStr = `IPCA + ${item.taxa_pct}%`;
      } else {
        taxaStr = `${item.taxa_pct}% a.a.`;
      }

      const vencStr = new Date(item.vencimento).toLocaleDateString('pt-BR');
      const vencCls = alertaVenc ? 'style="color:#8B1A1A;font-weight:700;"' : '';

      return `<tr>
        <td>
          <div style="font-weight:700;">${item.emissor}</div>
          <div style="font-size:10px;color:#888;">${item.tipo}</div>
        </td>
        <td><span class="pill p-blue">${item.indexador}</span></td>
        <td style="font-weight:600;">${taxaStr}</td>
        <td style="font-weight:600;color:#1E6E3A;">${rentAnual.toFixed(2)}% a.a.</td>
        <td>${fmtMoeda(item.valor_aplicado)}</td>
        <td style="color:#1E6E3A;">${fmtMoeda(rendMensal)}/mês</td>
        <td ${vencCls}>${vencStr}${alertaVenc ? ' ⚠' : ''}<br><small style="color:#888;">${diasParaVenc} dias</small></td>
        <td>
          <div style="display:flex;gap:4px;align-items:center;">
            <span class="pill ${item.liquidez === 'DIARIA' ? 'p-green' : 'p-gray'}">${item.liquidez}</span>
            ${item.fgc ? '<span class="pill p-blue">FGC</span>' : ''}
          </div>
        </td>
      </tr>`;
    });

    tbody.innerHTML = rows.join('');

    // Resumo
    resumo.innerHTML = `
      <div class="grid-4" style="margin-bottom:20px;">
        <div class="card">
          <div class="card-label">Total em Renda Fixa</div>
          <div class="card-value">${fmtMoeda(totalAplicado)}</div>
          <div class="card-sub">${itens.length} título(s)</div>
        </div>
        <div class="card">
          <div class="card-label">Renda Mensal Estimada</div>
          <div class="card-value green">${fmtMoeda(totalRendimento)}</div>
          <div class="card-sub pos">rendimento passivo</div>
        </div>
        <div class="card">
          <div class="card-label">CDI Atual</div>
          <div class="card-value">${cdi.toFixed(2)}%</div>
          <div class="card-sub">Selic ${selic}% - 0,10%</div>
        </div>
        <div class="card">
          <div class="card-label">IPCA 12m</div>
          <div class="card-value">${ipca}%</div>
          <div class="card-sub">inflação acumulada</div>
        </div>
      </div>
    `;

  } catch(e) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading">Erro ao carregar.</td></tr>';
  }
}

async function cadastrarRF() {
  const msg = document.getElementById('msg-rf');
  const emissor = document.getElementById('rf-emissor').value.trim();
  const tipo = document.getElementById('rf-tipo').value;
  const indexador = document.getElementById('rf-indexador').value;
  const taxa = parseFloat(document.getElementById('rf-taxa').value);
  const vencimento = document.getElementById('rf-vencimento').value;
  const valor = parseFloat(document.getElementById('rf-valor').value);
  const liquidez = document.getElementById('rf-liquidez').value;

  if (!emissor || !taxa || !vencimento || !valor) {
    msg.innerHTML = '<div class="alert alert-red">Preencha todos os campos obrigatórios.</div>';
    return;
  }

  try {
    const res = await fetch('/renda-fixa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ emissor, tipo, indexador, taxa_pct: taxa, vencimento, valor_aplicado: valor, liquidez })
    });
    const data = await res.json();
    if (res.ok) {
      msg.innerHTML = `<div class="alert alert-green">✓ ${data.mensagem}</div>`;
      document.getElementById('rf-emissor').value = '';
      document.getElementById('rf-taxa').value = '';
      document.getElementById('rf-vencimento').value = '';
      document.getElementById('rf-valor').value = '';
      carregarRendaFixa();
    } else {
      msg.innerHTML = `<div class="alert alert-red">✗ ${data.detail}</div>`;
    }
  } catch(e) {
    msg.innerHTML = '<div class="alert alert-red">Erro ao cadastrar.</div>';
  }
}

function atualizarLabelTaxa() {
  const indexador = document.getElementById('rf-indexador').value;
  const label = document.getElementById('rf-taxa-label');
  if (indexador === 'CDI') label.textContent = 'Taxa (% do CDI) — Ex: 110 para 110% CDI';
  else if (indexador === 'IPCA') label.textContent = 'Spread sobre IPCA (% a.a.) — Ex: 7 para IPCA+7%';
  else label.textContent = 'Taxa Prefixada (% a.a.) — Ex: 13.5';
}
