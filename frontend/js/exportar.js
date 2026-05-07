// ── EXPORTAR ──────────────────────────────────────────────

function exportarCarteira(formato) {
  window.location.href = `/exportar/carteira?formato=${formato}`;
}

function exportarWatchlist(formato) {
  window.location.href = `/exportar/watchlist?formato=${formato}`;
}

// ── IMPORTAR ──────────────────────────────────────────────

async function importarCarteira(input) {
  const file = input.files[0];
  if (!file) return;
  const msg = document.getElementById('msg-carteira');
  msg.innerHTML = '<div class="alert" style="background:#F5F3EE;color:#555;border-left:3px solid #888;">Importando...</div>';

  const form = new FormData();
  form.append('arquivo', file);
  try {
    const res  = await fetch('/importar/carteira', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok) {
      const errosTxt = data.erros.length ? ` · ${data.erros.length} erro(s)` : '';
      msg.innerHTML = `<div class="alert alert-green">
        ✓ ${data.importados} novos · ${data.atualizados} atualizados${errosTxt}
        ${data.erros.length ? '<br><small style="color:#888;">' + data.erros.slice(0,3).join(', ') + '</small>' : ''}
      </div>`;
      carregarCarteira();
    } else {
      msg.innerHTML = `<div class="alert alert-red">✗ ${data.detail}</div>`;
    }
  } catch(e) {
    msg.innerHTML = '<div class="alert alert-red">Erro ao enviar arquivo.</div>';
  }
  input.value = '';
}

async function importarWatchlist(input) {
  const file = input.files[0];
  if (!file) return;
  const msg = document.getElementById('msg-watchlist');
  msg.innerHTML = '<div class="alert" style="background:#F5F3EE;color:#555;border-left:3px solid #888;">Importando...</div>';

  const form = new FormData();
  form.append('arquivo', file);
  try {
    const res  = await fetch('/importar/watchlist', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok) {
      const errosTxt = data.erros.length ? ` · ${data.erros.length} erro(s)` : '';
      msg.innerHTML = `<div class="alert alert-green">
        ✓ ${data.importados} novos · ${data.atualizados} atualizados${errosTxt}
      </div>`;
      _radarCache.watchlist = null;
      carregarWatchlist();
    } else {
      msg.innerHTML = `<div class="alert alert-red">✗ ${data.detail}</div>`;
    }
  } catch(e) {
    msg.innerHTML = '<div class="alert alert-red">Erro ao enviar arquivo.</div>';
  }
  input.value = '';
}
