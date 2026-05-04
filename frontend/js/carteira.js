let ativoSelecionado = null;

async function carregarCarteira() {
  const tbody = document.getElementById('tabela-carteira');
  const msg = document.getElementById('msg-carteira');
  tbody.innerHTML = '<tr><td colspan="10" class="loading">Buscando preços em tempo real...</td></tr>';

  try {
    const ativos = await fetch('/ativos').then(r => r.json());

    if (!ativos.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="loading">Nenhum ativo cadastrado.</td></tr>';
      return;
    }

    tbody.innerHTML = ativos.map(a => {
      const varCls = a.variacao_dia >= 0 ? 'p-green' : 'p-red';
      const varSinal = a.variacao_dia >= 0 ? '▲ +' : '▼ ';
      const retCls = a.retorno_pct >= 0 ? 'p-green' : 'p-red';
      const retSinal = a.retorno_pct >= 0 ? '+' : '';
      const classePill = {ACAO:'p-gray',FII:'p-gold',ETF_BR:'p-blue',ETF_EUA:'p-green',TESOURO:'p-blue'}[a.classe] || 'p-gray';
      const nome = (a.nome || '').replace(/'/g, "\\'");

      return `<tr>
        <td><div class="ticker">${a.ticker}</div><div class="nome-dim">${a.nome || ''}</div></td>
        <td><span class="pill ${classePill}">${a.classe}</span></td>
        <td>${fmt(a.quantidade, 0)}</td>
        <td>${fmtMoeda(a.preco_medio)}</td>
        <td>${fmtMoeda(a.preco_atual)}</td>
        <td><span class="pill ${varCls}">${varSinal}${fmt(a.variacao_dia)}%</span></td>
        <td>${fmtMoeda(a.valor_investido)}</td>
        <td>${fmtMoeda(a.valor_atual)}</td>
        <td><span class="pill ${retCls}">${retSinal}${fmt(a.retorno_pct)}%</span></td>
        <td>
          <div style="display:flex;gap:4px;">
            <button onclick="abrirCompra('${a.ticker}','${nome}',${a.quantidade},${a.preco_medio},${a.preco_atual})"
              style="padding:3px 8px;font-size:10px;background:#1E6E3A;color:white;border:none;border-radius:4px;cursor:pointer;">+Compra</button>
            <button onclick="abrirVenda('${a.ticker}','${nome}',${a.quantidade},${a.preco_medio},${a.preco_atual})"
              style="padding:3px 8px;font-size:10px;background:#C8860A;color:white;border:none;border-radius:4px;cursor:pointer;">-Venda</button>
            <button onclick="excluirAtivo('${a.ticker}')"
              style="padding:3px 8px;font-size:10px;background:#8B1A1A;color:white;border:none;border-radius:4px;cursor:pointer;">✕</button>
          </div>
        </td>
      </tr>`;
    }).join('');
  } catch(e) {
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
      body: JSON.stringify({ ticker, quantidade, preco })
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
  } catch(e) { alert('Erro ao registrar compra.'); }
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
      body: JSON.stringify({ ticker, quantidade, preco })
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
  } catch(e) { alert('Erro ao registrar venda.'); }
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
  } catch(e) { alert('Erro ao remover ativo.'); }
}

function fecharModal(id) {
  document.getElementById(id).style.display = 'none';
}
