async function cadastrarAtivo() {
  const msg = document.getElementById('msg-cadastro');
  const ticker = document.getElementById('f-ticker').value.trim();
  const nome = document.getElementById('f-nome').value.trim();
  const classe = document.getElementById('f-classe').value;
  const mercado = document.getElementById('f-mercado').value;
  const quantidade = parseFloat(document.getElementById('f-quantidade').value);
  const preco = parseFloat(document.getElementById('f-preco').value);
  const dataCompra = document.getElementById('f-data').value;

  if (!ticker || !quantidade || !preco) {
    msg.innerHTML = '<div class="alert alert-red">Preencha Ticker, Quantidade e Preco Medio.</div>';
    return;
  }

  try {
    const body = { ticker, nome, classe, mercado, quantidade, preco_medio: preco };
    if (dataCompra) body.data_compra = dataCompra;

    const res = await fetch('/ativos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const resp = await res.json();

    if (res.ok) {
      msg.innerHTML = '<div class="alert alert-green">Ativo ' + ticker + ' cadastrado com sucesso!</div>';
      document.getElementById('f-ticker').value = '';
      document.getElementById('f-nome').value = '';
      document.getElementById('f-quantidade').value = '';
      document.getElementById('f-preco').value = '';
      document.getElementById('f-data').value = '';
    } else {
      msg.innerHTML = '<div class="alert alert-red">Erro: ' + resp.detail + '</div>';
    }
  } catch(e) {
    msg.innerHTML = '<div class="alert alert-red">Erro ao cadastrar ativo.</div>';
  }
}
