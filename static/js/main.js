// ── Busca ─────────────────────────────────────────────────────────────────────

async function buscar() {
  const termo     = document.getElementById('searchTerm')?.value?.trim();
  const tipo      = document.getElementById('searchType')?.value;
  const resultsDiv = document.getElementById('results');

  if (!termo || !resultsDiv) return;

  resultsDiv.innerHTML = `<div class="empty-msg">Buscando...</div>`;

  try {
    const url = `https://itunes.apple.com/search?term=${encodeURIComponent(termo)}&entity=${tipo}&limit=20`;
    const res  = await fetch(url);
    const data = await res.json();
    resultsDiv.innerHTML = '';

    if (!data.results.length) {
      resultsDiv.innerHTML = `<div class="empty-msg">Nenhum resultado encontrado</div>`;
      return;
    }

    data.results.forEach(item => {
      const trackId      = item.trackId || item.collectionId || '';
      const trackName    = item.trackName || item.collectionName || 'Sem título';
      const artistName   = item.artistName || 'Desconhecido';
      const artworkUrl100 = item.artworkUrl100 || '/static/img/default.png';

      const safeName   = trackName.replace(/'/g, "\\'").replace(/`/g, '\\`');
      const safeArtist = artistName.replace(/'/g, "\\'").replace(/`/g, '\\`');

      const card = document.createElement('div');
      card.className = 'media-card glass-soft';
      card.innerHTML = `
        <div style="position:relative">
          <img src="${artworkUrl100}" class="media-cover small-cover" loading="lazy"
               onerror="this.src='/static/img/default.png'">
          <button class="preview-play-btn" data-trackid="${trackId}"
            onclick="event.stopPropagation(); playPreview('${trackId}', '${safeName}', '${safeArtist}', '${artworkUrl100}', this)">
            <i class="ph-fill ph-play"></i>
          </button>
        </div>
        <div class="media-info">
          <div class="media-title clamp">${trackName}</div>
          <div class="media-artist small-dim">${artistName}</div>
        </div>
        <div class="media-actions-row">
          <button class="btn-pill" onclick="verAlbum('${trackId}')">
            <i class="ph ph-play" style="font-size:12px"></i> Ver
          </button>
          <button class="btn-pill" onclick="toggleFavoriteFromData('${trackId}','${safeName}','${safeArtist}','${artworkUrl100}')">
            <i class="ph ph-heart" style="font-size:12px"></i>
          </button>
          <div class="rating-stars" data-id="${trackId}" style="display:flex;gap:2px">
            ${[1,2,3,4,5].map(n =>
              `<span class="star" onclick="avaliar('${trackId}',${n},'${safeName}','${safeArtist}','${artworkUrl100}',this)">★</span>`
            ).join('')}
          </div>
        </div>
      `;

      resultsDiv.appendChild(card);
    });
  } catch (err) {
    console.error(err);
    resultsDiv.innerHTML = `<div class="empty-msg">Erro na busca</div>`;
  }
}


// ── Navegação ─────────────────────────────────────────────────────────────────

function verAlbum(id) {
  window.location = `/album/${id}`;
}


// ── Toggle favorito ───────────────────────────────────────────────────────────

async function toggleFavoriteFromData(trackId, trackName, artistName, artworkUrl100) {
  try {
    const res  = await fetch('/favorite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trackId, trackName, artistName, artworkUrl100 })
    });
    const data = await res.json();

    if (data.error === 'not_logged_in') return alert('Faça login!');

    showToast(data.status === 'favorited' ? 'Adicionado aos favoritos' : 'Removido dos favoritos');
  } catch (err) {
    console.error(err);
  }
}


// ── Avaliar ───────────────────────────────────────────────────────────────────

async function avaliar(trackId, rating, trackName, artistName, artworkUrl100, starEl) {
  try {
    const res = await fetch('/rate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trackId, rating, trackName, artistName, artworkUrl100 })
    });

    if (!res.ok) return alert('Erro ao avaliar');

    if (starEl?.closest) {
      const container = starEl.closest('.rating-stars');
      container.querySelectorAll('.star')
        .forEach((s, i) => s.classList.toggle('filled', i < rating));
    }

    showToast(`Nota: ${rating}`);
  } catch (err) {
    console.error(err);
  }
}


// ── Logout ────────────────────────────────────────────────────────────────────

async function logout() {
  await fetch('/logout', { method: 'POST' });
  location.href = '/login';
}


// ── Toast ─────────────────────────────────────────────────────────────────────

function showToast(msg) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.innerHTML = `<i class="ph ph-check-circle" style="font-size:15px;color:var(--accent-lt)"></i> ${msg}`;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2800);
}


// ── Avaliações recentes ───────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const box = document.getElementById('recent-ratings');
  if (!box) return;

  fetch('/recent_ratings')
    .then(r => r.json())
    .then(data => {
      if (!data.length) {
        box.innerHTML = `<div class="empty-msg">Nenhuma nota ainda</div>`;
        return;
      }

      box.innerHTML = data.map(i => {
        const safeName   = (i.trackName || '').replace(/'/g, "\\'").replace(/`/g, '\\`');
        const safeArtist = (i.artistName || '').replace(/'/g, "\\'").replace(/`/g, '\\`');

        return `
        <div class="media-card glass-soft" style="cursor:pointer">
          <div style="position:relative" onclick="verAlbum('${i.trackId}')">
            <img src="${i.artworkUrl100}" class="media-cover small-cover"
                 onerror="this.src='/static/img/default.png'">
            <button class="preview-play-btn" data-trackid="${i.trackId}"
              onclick="event.stopPropagation(); playPreview('${i.trackId}', '${safeName}', '${safeArtist}', '${i.artworkUrl100}', this)">
              <i class="ph-fill ph-play"></i>
            </button>
          </div>
          <div class="media-info" onclick="verAlbum('${i.trackId}')">
            <div class="media-title clamp">${i.trackName}</div>
            <div class="media-artist small-dim">${i.artistName}</div>
            <div style="display:flex;gap:2px;margin-top:4px">
              ${[1,2,3,4,5].map(n =>
                `<span class="star ${i.rating >= n ? 'filled' : ''}" style="font-size:13px;cursor:default">★</span>`
              ).join('')}
            </div>
          </div>
        </div>`;
      }).join('');
    })
    .catch(() => {
      box.innerHTML = `<div class="empty-msg">Erro ao carregar notas</div>`;
    });
});