let ativoSelecionado = null;

async function carregarCarteira() {
  const tbody = document.getElementById('tabela-carteira');
  tbody.innerHTML = '<tr><td colspan="10" class="loading">Buscando preços em tempo real...</td></tr>';

  try {
    const ativos = await fetch('/ativos').then(r => r.json());

    if (!ativos.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="loading">Nenhum ativo cadastrado.</td></tr>';
      return;
    }

    // Agrupa: classe → segmento → [ativos]
    const byClasse = {};
    ativos.forEach(a => {
      if (!byClasse[a.classe]) byClasse[a.classe] = {};
      const seg = a.segmento || 'OUTROS';
      if (!byClasse[a.classe][seg]) byClasse[a.classe][seg] = [];
      byClasse[a.classe][seg].push(a);
    });

    const allClasses = Object.keys(byClasse);
    const orderedClasses = [
      ...CLASSE_ORDER.filter(c => allClasses.includes(c)),
      ...allClasses.filter(c => !CLASSE_ORDER.includes(c)),
    ];

    let html = '';

    orderedClasses.forEach(classe => {
      const bySegmento = byClasse[classe];

      Object.entries(bySegmento).forEach(([segmento, items]) => {
        const subtotalInv = items.reduce((s, a) => s + a.valor_investido, 0);
        const subtotalAtu = items.reduce((s, a) => s + a.valor_atual, 0);
        const subtotalRet = subtotalInv > 0
          ? (subtotalAtu - subtotalInv) / subtotalInv * 100 : 0;
        const subtotalRS  = subtotalAtu - subtotalInv;

        const label   = SEGMENTO_LABELS[segmento] || segmento;
        const rCls    = subtotalRet >= 0 ? 'p-green' : 'p-red';
        const rSinal  = subtotalRet >= 0 ? '+' : '';
        const rsCor   = subtotalRS  >= 0 ? '#1E6E3A' : '#8B1A1A';
        const rsSinal = subtotalRS  >= 0 ? '+' : '';
        const n       = items.length;

        html += `<tr class="grupo-header">
          <td class="grupo-label" colspan="6">${label}
            <span class="grupo-count">${n} ativo${n !== 1 ? 's' : ''}</span>
          </td>
          <td class="grupo-num">${fmtMoeda(subtotalInv)}</td>
          <td class="grupo-num">${fmtMoeda(subtotalAtu)}</td>
          <td class="grupo-num">
            <span class="pill ${rCls}">${rSinal}${fmt(subtotalRet)}%</span>
            <div style="font-size:10px;color:${rsCor};margin-top:2px;">${rsSinal}${fmtMoeda(Math.abs(subtotalRS))}</div>
          </td>
          <td class="grupo-num"></td>
        </tr>`;

        items.forEach(a => {
          const varCls  = a.variacao_dia >= 0 ? 'p-green' : 'p-red';
          const varSin  = a.variacao_dia >= 0 ? '▲ +' : '▼ ';
          const retCls  = a.retorno_pct  >= 0 ? 'p-green' : 'p-red';
          const retSin  = a.retorno_pct  >= 0 ? '+' : '';
          const cpill   = {ACAO:'p-gray',FII:'p-gold',ETF_BR:'p-blue',ETF_EUA:'p-green',
                           TESOURO:'p-blue',FUNDO_INVEST:'p-gray'}[a.classe] || 'p-gray';
          const nome      = (a.nome || '').replace(/'/g, "\\'");
          const dataCompra = a.data_compra || '';

          const btnPreco = a.classe === 'FUNDO_INVEST' ? `
            <button onclick="abrirPrecoManual('${a.ticker}',${a.preco_atual})"
              style="padding:3px 8px;font-size:10px;background:#1A5C8A;color:white;border:none;border-radius:4px;cursor:pointer;">Preço</button>
          ` : '';

          html += `<tr>
            <td><div class="ticker">${a.ticker}</div><div class="nome-dim">${a.nome || ''}</div></td>
            <td><span class="pill ${cpill}">${a.classe}</span></td>
            <td>${fmt(a.quantidade, 0)}</td>
            <td>${fmtMoeda(a.preco_medio)}</td>
            <td>${fmtMoeda(a.preco_atual)}</td>
            <td><span class="pill ${varCls}">${varSin}${fmt(a.variacao_dia)}%</span></td>
            <td>${fmtMoeda(a.valor_investido)}</td>
            <td>${fmtMoeda(a.valor_atual)}</td>
            <td><span class="pill ${retCls}">${retSin}${fmt(a.retorno_pct)}%</span></td>
            <td>
              <div style="display:flex;gap:4px;flex-wrap:wrap;">
                ${btnPreco}
                <button onclick="abrirCompra('${a.ticker}','${nome}',${a.quantidade},${a.preco_medio},${a.preco_atual})"
                  style="padding:3px 8px;font-size:10px;background:#1E6E3A;color:white;border:none;border-radius:4px;cursor:pointer;">+Compra</button>
                <button onclick="abrirVenda('${a.ticker}','${nome}',${a.quantidade},${a.preco_medio},${a.preco_atual})"
                  style="padding:3px 8px;font-size:10px;background:#C8860A;color:white;border:none;border-radius:4px;cursor:pointer;">-Venda</button>
                <button onclick="abrirEdicao('${a.ticker}','${nome}','${a.classe}','${a.mercado}',${a.quantidade},${a.preco_medio},'${a.moeda}','${dataCompra}')"
                  style="padding:3px 8px;font-size:10px;background:#1A5C8A;color:white;border:none;border-radius:4px;cursor:pointer;">✎</button>
                <button onclick="excluirAtivo('${a.ticker}')"
                  style="padding:3px 8px;font-size:10px;background:#8B1A1A;color:white;border:none;border-radius:4px;cursor:pointer;">✕</button>
              </div>
            </td>
          </tr>`;
        });
      });
    });

    tbody.innerHTML = html;
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="10" class="loading">Erro ao carregar carteira.</td></tr>';
  }
}

function abrirCompra(ticker, nome, qtd, precoMedio, precoAtual) {
  ativoSelecionado = { ticker, qtd, precoMedio, precoAtual };
  document.getElementById('modal-compra-ticker').textContent = `${ticker} · ${qtd} cotas · PM R$ ${precoMedio}`;
  document.getElementById('compra-quantidade').value = '';
  document.getElementById('compra-preco').value = precoAtual;
  document.getElementById('compra-preview').innerHTML = '';
  document.getElementById('modal-compra').style.display = 'flex';
  document.getElementById('compra-quantidade').oninput = calcularPreviewCompra;
  document.getElementById('compra-preco').oninput = calcularPreviewCompra;
}

function calcularPreviewCompra() {
  const a = ativoSelecionado;
  const qtdNova = parseFloat(document.getElementById('compra-quantidade').value) || 0;
  const preco = parseFloat(document.getElementById('compra-preco').value) || 0;
  if (!qtdNova || !preco) return;
  const custoAtual = a.qtd * a.precoMedio;
  const custoNovo = qtdNova * preco;
  const novaQtd = a.qtd + qtdNova;
  const novopm = (custoAtual + custoNovo) / novaQtd;
  document.getElementById('compra-preview').innerHTML = `
    <strong>Resultado após a compra:</strong><br>
    Cotas: ${a.qtd} → <strong>${novaQtd}</strong><br>
    Preço médio: R$ ${a.precoMedio} → <strong>R$ ${novopm.toFixed(2)}</strong><br>
    Custo total: <strong>R$ ${(custoAtual + custoNovo).toFixed(2)}</strong>
  `;
}

async function confirmarCompra() {
  const ticker = ativoSelecionado.ticker;
  const quantidade = parseFloat(document.getElementById('compra-quantidade').value);
  const preco = parseFloat(document.getElementById('compra-preco').value);
  if (!quantidade || !preco) return;
  try {
    const res = await fetch('/ativos/compra', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, quantidade, preco }),
    });
    const data = await res.json();
    if (res.ok) {
      fecharModal('modal-compra');
      document.getElementById('msg-carteira').innerHTML =
        `<div class="alert alert-green">✓ ${data.mensagem} · Novo PM: R$ ${data.preco_medio_novo}</div>`;
      carregarCarteira();
    } else {
      alert(data.detail);
    }
  } catch (e) { alert('Erro ao registrar compra.'); }
}

function abrirVenda(ticker, nome, qtd, precoMedio, precoAtual) {
  ativoSelecionado = { ticker, qtd, precoMedio, precoAtual };
  document.getElementById('modal-venda-ticker').textContent = `${ticker} · ${qtd} cotas · PM R$ ${precoMedio}`;
  document.getElementById('venda-quantidade').value = '';
  document.getElementById('venda-preco').value = precoAtual;
  document.getElementById('venda-preview').innerHTML = '';
  document.getElementById('modal-venda').style.display = 'flex';
  document.getElementById('venda-quantidade').oninput = calcularPreviewVenda;
  document.getElementById('venda-preco').oninput = calcularPreviewVenda;
}

function calcularPreviewVenda() {
  const a = ativoSelecionado;
  const qtdVenda = parseFloat(document.getElementById('venda-quantidade').value) || 0;
  const preco = parseFloat(document.getElementById('venda-preco').value) || 0;
  if (!qtdVenda || !preco) return;
  const lucro = (preco - a.precoMedio) * qtdVenda;
  const lucropct = ((preco - a.precoMedio) / a.precoMedio * 100);
  const cor = lucro >= 0 ? '#1E6E3A' : '#8B1A1A';
  document.getElementById('venda-preview').innerHTML = `
    <strong>Resultado da venda:</strong><br>
    Cotas vendidas: <strong>${qtdVenda}</strong> de ${a.qtd}<br>
    Cotas restantes: <strong>${a.qtd - qtdVenda}</strong><br>
    Lucro/Prejuízo: <strong style="color:${cor}">R$ ${lucro.toFixed(2)} (${lucropct.toFixed(2)}%)</strong>
  `;
}

async function confirmarVenda() {
  const ticker = ativoSelecionado.ticker;
  const quantidade = parseFloat(document.getElementById('venda-quantidade').value);
  const preco = parseFloat(document.getElementById('venda-preco').value);
  if (!quantidade || !preco) return;
  try {
    const res = await fetch('/ativos/venda', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, quantidade, preco }),
    });
    const data = await res.json();
    if (res.ok) {
      fecharModal('modal-venda');
      const lucroStr = data.lucro_realizado >= 0
        ? `+R$ ${data.lucro_realizado}` : `-R$ ${Math.abs(data.lucro_realizado)}`;
      document.getElementById('msg-carteira').innerHTML =
        `<div class="alert alert-green">✓ ${data.mensagem} · Lucro: ${lucroStr} (${data.lucro_pct}%)</div>`;
      carregarCarteira();
    } else {
      alert(data.detail);
    }
  } catch (e) { alert('Erro ao registrar venda.'); }
}

async function excluirAtivo(ticker) {
  if (!confirm(`Remover ${ticker} da carteira?`)) return;
  try {
    const res = await fetch(`/ativos/${ticker}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) {
      document.getElementById('msg-carteira').innerHTML =
        `<div class="alert alert-green">✓ ${data.mensagem}</div>`;
      carregarCarteira();
    }
  } catch (e) { alert('Erro ao remover ativo.'); }
}

function fecharModal(id) {
  document.getElementById(id).style.display = 'none';
}

function abrirPrecoManual(ticker, precoAtual) {
  ativoSelecionado = { ticker };
  document.getElementById('modal-preco-ticker').textContent = `${ticker} · Preço atual: R$ ${precoAtual}`;
  document.getElementById('preco-novo-valor').value = precoAtual;
  document.getElementById('modal-preco').style.display = 'flex';
}

function abrirEdicao(ticker, nome, classe, mercado, quantidade, precoMedio, moeda, dataCompra) {
  ativoSelecionado = { ticker };
  document.getElementById('edit-ticker-titulo').textContent = ticker;
  document.getElementById('edit-nome').value = nome;
  document.getElementById('edit-classe').value = classe;
  document.getElementById('edit-mercado').value = mercado;
  document.getElementById('edit-quantidade').value = quantidade;
  document.getElementById('edit-preco-medio').value = precoMedio;
  document.getElementById('edit-moeda').value = moeda;
  document.getElementById('edit-data-compra').value = dataCompra;
  document.getElementById('modal-editar').style.display = 'flex';
}

async function confirmarEdicao() {
  const ticker = ativoSelecionado.ticker;
  const body = {
    nome:        document.getElementById('edit-nome').value || null,
    classe:      document.getElementById('edit-classe').value || null,
    mercado:     document.getElementById('edit-mercado').value || null,
    quantidade:  parseFloat(document.getElementById('edit-quantidade').value) || null,
    preco_medio: parseFloat(document.getElementById('edit-preco-medio').value) || null,
    moeda:       document.getElementById('edit-moeda').value || null,
    data_compra: document.getElementById('edit-data-compra').value || null,
  };
  try {
    const res = await fetch(`/ativos/${ticker}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (res.ok) {
      fecharModal('modal-editar');
      document.getElementById('msg-carteira').innerHTML =
        `<div class="alert alert-green">✓ ${data.mensagem}</div>`;
      carregarCarteira();
    } else {
      alert(data.detail || 'Erro ao editar ativo.');
    }
  } catch (e) { alert('Erro ao editar ativo.'); }
}

async function confirmarPrecoManual() {
  const ticker = ativoSelecionado.ticker;
  const preco = parseFloat(document.getElementById('preco-novo-valor').value);
  if (!preco) return;
  try {
    const res = await fetch(`/ativos/${ticker}/preco`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preco }),
    });
    if (res.ok) {
      fecharModal('modal-preco');
      carregarCarteira();
    } else {
      const data = await res.json();
      alert(data.detail);
    }
  } catch (e) { alert('Erro ao atualizar preço.'); }
}
