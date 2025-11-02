// ====================================================== 
// BUSCA ( Landing page )
// ======================================================
async function buscar() {
  const termo = document.getElementById('searchTerm')?.value?.trim();
  const tipo = document.getElementById('searchType')?.value;
  const resultsDiv = document.getElementById('results');

  if (!termo || !resultsDiv) return;

  resultsDiv.innerHTML = `<div class="loading">🔎 Buscando...</div>`;

  try {
    const url = `https://itunes.apple.com/search?term=${encodeURIComponent(termo)}&entity=${tipo}&limit=20`;
    const res = await fetch(url);
    const data = await res.json();
    resultsDiv.innerHTML = '';

    if (!data.results.length) {
      resultsDiv.innerHTML = `<div class="empty-msg">Nenhum resultado encontrado 😢</div>`;
      return;
    }

    data.results.forEach(item => {
      const trackId = item.trackId || item.collectionId || '';
      const trackName = item.trackName || item.collectionName || 'Sem título';
      const artistName = item.artistName || 'Desconhecido';
      const artworkUrl100 = item.artworkUrl100 || '/static/img/placeholder.png';

      const card = document.createElement('div');
      card.className = 'media-card glass-soft';
      card.innerHTML = `
        <img src="${artworkUrl100}" class="media-cover small-cover">
        <div class="media-info">
          <div class="media-title clamp">${trackName}</div>
          <div class="media-artist small-dim">${artistName}</div>
        </div>

        <div class="media-actions-row">
          <button class="btn-ghost" onclick="verAlbum('${trackId}')">▶ Ver</button>

          <button class="btn-ghost"
            onclick="toggleFavoriteFromData(
              '${trackId}',
              '${trackName.replace(/'/g,"\\'")}',
              '${artistName.replace(/'/g,"\\'")}',
              '${artworkUrl100}'
            )">
            ❤️
          </button>

          <div class="rating-stars" data-id="${trackId}">
            ${[1,2,3,4,5].map(n =>
              `<span class="star" onclick="avaliar('${trackId}',${n},'${trackName}','${artistName}','${artworkUrl100}',this)">★</span>`
            ).join('')}
          </div>
        </div>
      `;

      resultsDiv.appendChild(card);
    });
  } catch (err) {
    console.error(err);
    resultsDiv.innerHTML = `<div class="error-msg">Erro na busca 😢</div>`;
  }
}

// ======================================================
// NAVEGAÇÃO PARA ÁLBUM
// ======================================================
function verAlbum(id) {
  window.location = `/album/${id}`;
}

// ======================================================
// TOGGLE FAVORITO
// ======================================================
async function toggleFavoriteFromData(trackId, trackName, artistName, artworkUrl100) {
  try {
    const res = await fetch('/favorite', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ trackId, trackName, artistName, artworkUrl100 })
    });
    const data = await res.json();

    if (data.error === 'not_logged_in') return alert('Faça login!');

    if (data.status === 'favorited')
      showToast(`❤️ Adicionado aos favoritos`);
    else
      showToast(`💔 Removido dos favoritos`);
  } catch (err) {
    console.error(err);
  }
}

// ======================================================
// AVALIAR (RATING)
// ======================================================
async function avaliar(trackId, rating, trackName, artistName, artworkUrl100, starEl) {
  try {
    const res = await fetch('/rate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trackId, rating, trackName, artistName, artworkUrl100 })
    });

    if (!res.ok) return alert("Erro ao avaliar");

    if (starEl?.closest) {
      const container = starEl.closest('.rating-stars');
      container.querySelectorAll('.star')
        .forEach((s, i) => s.classList.toggle('filled', i < rating));
    }

    showToast(`⭐ Nota: ${rating}`);
  } catch (err) {
    console.error(err);
  }
}

// ======================================================
// LOGOUT
// ======================================================
async function logout() {
  await fetch('/logout');
  location.href = '/login';
}

// ======================================================
// TOAST
// ======================================================
function showToast(msg) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.innerText = msg;
  document.body.appendChild(t);

  setTimeout(() => t.classList.add('show'), 50);
  setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => t.remove(), 300);
  }, 2500);
}

// ======================================================
// RECENT RATINGS (landing)
// ======================================================
document.addEventListener('DOMContentLoaded', () => {
  const box = document.getElementById('recent-ratings');
  if (!box) return;

  fetch('/recent_ratings')
    .then(r => r.json())
    .then(data => {
      if (!data.length) {
        box.innerHTML = `<div class="empty-msg">Nenhuma nota ainda 👀</div>`;
        return;
      }

      box.innerHTML = data.map(i => `
        <div class="media-card glass-soft">
          <img src="${i.artworkUrl100}" class="media-cover small-cover">
          <div class="media-info">
            <div class="media-title clamp">${i.trackName}</div>
            <div class="media-artist small-dim">${i.artistName}</div>
            <div class="rating-stars small">
              ${[1,2,3,4,5].map(n =>
                `<span class="star ${i.rating>=n?'filled':''}">★</span>`
              ).join('')}
            </div>
          </div>
        </div>
      `).join('');
    });
});
