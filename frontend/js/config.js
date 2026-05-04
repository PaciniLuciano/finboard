async function carregarConfig() {
  try {
    const r = await fetch('/configuracoes').then(r => r.json());
    if (r.selic_previsao_12m) {
      document.getElementById('cfg-selic-previsao').value = r.selic_previsao_12m;
    }
    if (r.selic_pessimista) {
      document.getElementById('cfg-selic-pessimista').value = r.selic_pessimista;
    }
    if (r.selic_otimista) {
      document.getElementById('cfg-selic-otimista').value = r.selic_otimista;
    }
    if (r.fonte_selic) {
      document.querySelector(`input[name="fonte-selic"][value="${r.fonte_selic}"]`).checked = true;
    }
    await atualizarImpacto();
  } catch(e) {}
}

async function salvarConfig() {
  const previsao = parseFloat(document.getElementById('cfg-selic-previsao').value);
  const pessimista = parseFloat(document.getElementById('cfg-selic-pessimista').value);
  const otimista = parseFloat(document.getElementById('cfg-selic-otimista').value);
  const fonte = document.querySelector('input[name="fonte-selic"]:checked').value;

  if (!previsao || !pessimista || !otimista) {
    document.getElementById('msg-config').innerHTML =
      '<div class="alert alert-red">Preencha todos os campos de Selic.</div>';
    return;
  }

  try {
    const res = await fetch('/configuracoes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        selic_previsao_12m: previsao,
        selic_pessimista: pessimista,
        selic_otimista: otimista,
        fonte_selic: fonte
      })
    });

    if (res.ok) {
      document.getElementById('msg-config').innerHTML =
        '<div class="alert alert-green">✓ Configurações salvas. Scores serão recalculados com novo cenário.</div>';
      await atualizarImpacto();
    }
  } catch(e) {
    document.getElementById('msg-config').innerHTML =
      '<div class="alert alert-red">Erro ao salvar configurações.</div>';
  }
}

async function atualizarImpacto() {
  const previsao = parseFloat(document.getElementById('cfg-selic-previsao').value) || null;
  const pessimista = parseFloat(document.getElementById('cfg-selic-pessimista').value) || null;
  const otimista = parseFloat(document.getElementById('cfg-selic-otimista').value) || null;

  try {
    const macro = await fetch('/macro/regime').then(r => r.json());
    const selicAtual = macro.detalhes.selic_atual;
    const ipca = macro.detalhes.ipca_12m;

    const calcRegime = (selic) => {
      const jurosReal = selic - ipca;
      if (selic > 13) return { regime: 'DEFENSIVO', cor: '#8B1A1A' };
      if (selic > 11) return { regime: 'NEUTRO', cor: '#C8860A' };
      return { regime: 'AGRESSIVO', cor: '#1E6E3A' };
    };

    const calcScores = (regime) => {
      const scores = {
        'DEFENSIVO': { ACAO: 4.0, FII_TIJOLO: 4.0, FII_PAPEL: 8.5, RF: 9.0 },
        'NEUTRO':    { ACAO: 6.0, FII_TIJOLO: 6.0, FII_PAPEL: 7.0, RF: 7.5 },
        'AGRESSIVO': { ACAO: 8.5, FII_TIJOLO: 8.5, FII_PAPEL: 5.5, RF: 6.0 },
      };
      return scores[regime] || scores['NEUTRO'];
    };

    const cenarios = [
      {
        label: 'Atual',
        selic: selicAtual,
        ...calcRegime(selicAtual),
        fonte: 'Banco Central'
      },
      {
        label: 'Sua Previsão (12m)',
        selic: previsao,
        ...(previsao ? calcRegime(previsao) : { regime: '—', cor: '#888' }),
        fonte: 'Manual'
      },
      {
        label: 'Focus (12m)',
        selic: macro.detalhes.focus_selic_esperada,
        ...(macro.detalhes.focus_selic_esperada
          ? calcRegime(macro.detalhes.focus_selic_esperada)
          : { regime: 'Indisponível', cor: '#888' }),
        fonte: 'Banco Central'
      },
      {
        label: 'Pessimista',
        selic: pessimista,
        ...(pessimista ? calcRegime(pessimista) : { regime: '—', cor: '#888' }),
        fonte: 'Seu cenário'
      },
      {
        label: 'Otimista',
        selic: otimista,
        ...(otimista ? calcRegime(otimista) : { regime: '—', cor: '#888' }),
        fonte: 'Seu cenário'
      },
    ];

    let html = `
      <div class="section-title" style="margin-top:24px;">Impacto dos Cenários no Score Macro</div>
      <div style="overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <thead>
          <tr style="background:#F5F3EE;">
            <th style="padding:10px 14px;text-align:left;border-bottom:1px solid #DDD9D0;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:#888;">Cenário</th>
            <th style="padding:10px 14px;text-align:center;border-bottom:1px solid #DDD9D0;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:#888;">Selic</th>
            <th style="padding:10px 14px;text-align:center;border-bottom:1px solid #DDD9D0;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:#888;">Regime</th>
            <th style="padding:10px 14px;text-align:center;border-bottom:1px solid #DDD9D0;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:#888;">Ações</th>
            <th style="padding:10px 14px;text-align:center;border-bottom:1px solid #DDD9D0;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:#888;">FII Tijolo</th>
            <th style="padding:10px 14px;text-align:center;border-bottom:1px solid #DDD9D0;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:#888;">FII Papel</th>
            <th style="padding:10px 14px;text-align:center;border-bottom:1px solid #DDD9D0;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:#888;">Renda Fixa</th>
            <th style="padding:10px 14px;text-align:left;border-bottom:1px solid #DDD9D0;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:#888;">Fonte</th>
          </tr>
        </thead>
        <tbody>
    `;

    cenarios.forEach((c, i) => {
      const scores = c.selic ? calcScores(c.regime) : {};
      const bg = i === 0 ? '#F9F7F4' : 'white';
      const bold = i === 0 ? 'font-weight:700;' : '';
      html += `
        <tr style="background:${bg};">
          <td style="padding:10px 14px;border-bottom:1px solid #F0EDE6;${bold}">${c.label}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #F0EDE6;text-align:center;font-family:monospace;${bold}">${c.selic ? c.selic + '%' : '—'}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #F0EDE6;text-align:center;">
            <span style="color:${c.cor};font-weight:700;font-size:11px;">${c.regime}</span>
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid #F0EDE6;text-align:center;">${scores.ACAO || '—'}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #F0EDE6;text-align:center;">${scores.FII_TIJOLO || '—'}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #F0EDE6;text-align:center;">${scores.FII_PAPEL || '—'}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #F0EDE6;text-align:center;">${scores.RF || '—'}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #F0EDE6;font-size:11px;color:#888;">${c.fonte}</td>
        </tr>`;
    });

    html += '</tbody></table></div>';
    document.getElementById('cenarios-impacto').innerHTML = html;

  } catch(e) {
    document.getElementById('cenarios-impacto').innerHTML =
      '<div class="loading">Erro ao calcular impacto dos cenários.</div>';
  }
}
