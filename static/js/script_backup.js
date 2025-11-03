
async function api(url, method='GET', data=null) {
  const opts = { method, headers:{'Content-Type':'application/json'} };
  if(data) opts.body = JSON.stringify(data);
  const res = await fetch(url, opts);
  return res.json();
}

function escapeHtml(s){
  if(!s) return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function escapeQuotes(s){
  return (s||'').replace(/'/g,"\\'").replace(/\"/g,'\\\"');
}

function lean(it){
  return {
    trackId: String(it.trackId || it.collectionId || it.artistId || (it.artistName+it.trackName)),
    trackName: it.trackName || it.collectionName || '',
    collectionName: it.collectionName || '',
    artistName: it.artistName || '',
    artworkUrl100: it.artworkUrl100 || it.artworkUrl60 || '',
    previewUrl: it.previewUrl || null
  };
}

// ================== DOM refs ==================
const authSection   = document.getElementById('auth-section');
const appSection    = document.getElementById('app-section');
const authMsg       = document.getElementById('auth-msg');
const usernameIn    = document.getElementById('username');
const passwordIn    = document.getElementById('password');
const btnLogin      = document.getElementById('btn-login');
const btnRegister   = document.getElementById('btn-register');
const btnLogout     = document.getElementById('btn-logout');

const whoamiDisplay = document.getElementById('whoami-display');

const qInput        = document.getElementById('q');
const entitySelect  = document.getElementById('entity');
const btnSearch     = document.getElementById('btn');

const resultsDiv    = document.getElementById('results');
const libraryDiv    = document.getElementById('library');
const countBadge    = document.getElementById('count');
const favoritesDiv  = document.getElementById('favorites');
const recentDiv     = document.getElementById('recent');

const audio         = document.getElementById('audio');
const nowDiv        = document.getElementById('now');
const lyricsDiv     = document.getElementById('lyrics');

// ================== Auth ==================
async function doLogin(){
  const u = usernameIn.value.trim();
  const p = passwordIn.value.trim();
  if(!u||!p){ authMsg.textContent='Preencha usuário e senha'; return; }
  const r = await api('/login','POST',{username:u,password:p});
  if(r.error){ authMsg.textContent = r.error; return; }
  authMsg.textContent='';
  await enterApp();
}

async function doRegister(){
  const u = usernameIn.value.trim();
  const p = passwordIn.value.trim();
  if(!u||!p){ authMsg.textContent='Preencha usuário e senha'; return; }
  const r = await api('/register','POST',{username:u,password:p});
  if(r.error){ authMsg.textContent = r.error; return; }
  authMsg.textContent='Registrado! Agora faça login.';
}

async function doLogout(){
  await api('/logout','POST');
  location.reload();
}

btnLogin.addEventListener('click', doLogin);
btnRegister.addEventListener('click', doRegister);
btnLogout.addEventListener('click', doLogout);

async function enterApp(){
  const w = await api('/whoami','GET');
  if(!w.username){
    // não logado
    authSection.style.display='block';
    appSection.style.display='none';
    whoamiDisplay.textContent='-';
    return;
  }
  whoamiDisplay.textContent = w.username;
  authSection.style.display='none';
  appSection.style.display='block';
  await refreshAll();
}

//  APIs
async function itunesSearch(term, entity='song'){
  const url = `https://itunes.apple.com/search?term=${encodeURIComponent(term)}&entity=${entity}&limit=25`;
  const res = await fetch(url);
  if(!res.ok) throw new Error(res.status+' '+res.statusText);
  const j = await res.json();
  return j.results || [];
}

async function fetchLyricsApi(artist,title){
  try{
    const url = `https://api.lyrics.ovh/v1/${encodeURIComponent(artist)}/${encodeURIComponent(title)}`;
    const r = await fetch(url);
    if(!r.ok) return null;
    const j = await r.json();
    return j.lyrics || null;
  }catch(e){
    return null;
  }
}


async function playPreview(url, title, artist){
  audio.src = url;
  try{ await audio.play(); }catch(e){}
  nowDiv.innerHTML = `<strong>${escapeHtml(title)}</strong> — ${escapeHtml(artist)}`;
  await api('/recent','POST',{name:`${title} — ${artist}`});
  await renderRecent();
}

async function showLyrics(artist, title){
  lyricsDiv.textContent = 'Buscando letras...';
  const l = await fetchLyricsApi(artist,title);
  if(l){
    lyricsDiv.innerHTML = `<pre style="white-space:pre-wrap;">${escapeHtml(l)}</pre>`;
  } else {
    lyricsDiv.innerHTML = '<div class="small">Letra não encontrada.</div>';
  }
}

// ================== Biblioteca ==================
async function fetchLibrary(){
  const r = await api('/library','GET');
  if(r.error){ return []; }
  return r;
}

function renderStarRowHTML(trackId, currentRating){
  let out = '';
  for(let i=1;i<=5;i++){
    out += `<span class="star ${i<=currentRating?'':'gray'}" data-rate="${i}" data-track="${trackId}">★</span>`;
  }
  return out;
}

function attachStarHandlers(){
  document.querySelectorAll('.stars-row .star').forEach(st=>{
    st.addEventListener('click', async ()=>{
      const rateVal = Number(st.getAttribute('data-rate'));
      const tid = st.getAttribute('data-track');
      await api('/rate','POST',{trackId:tid,rating:rateVal});
      // força reload biblioteca
      await renderLibrary();
    });
  });
}

async function renderLibrary(){
  const lib = await fetchLibrary();
  countBadge.textContent = lib.length;

  if(!lib.length){
    libraryDiv.innerHTML = '<p class="small">Biblioteca vazia. Use 💾 para salvar.</p>';
    return;
  }

  libraryDiv.innerHTML = lib.map(item=>{
    const stars = renderStarRowHTML(item.trackId, item.rating || 0);
    return `
      <div class="track" style="align-items:flex-start;">
        <img class="thumb" src="${item.artworkUrl100||''}" onerror="this.style.display='none'"/>
        <div class="meta" style="flex:1">
          <div style="font-weight:600">${escapeHtml(item.trackName||item.collectionName||'—')}</div>
          <div class="small">${escapeHtml(item.artistName||'')}</div>

          <div class="small" style="margin-top:4px">
            Avaliação atual: <span>${item.rating || '—'}</span>/5
          </div>

          <div class="stars-row" data-trackid="${item.trackId}">
            ${stars}
          </div>

          <div style="margin-top:6px">
            <a class="small" style="color:#9fb0c8;text-decoration:underline"
               href="/album/${encodeURIComponent(item.trackId)}" target="_blank">
               Ver página →
            </a>
          </div>
        </div>
        <div class="actions" style="gap:4px">
          ${item.previewUrl ? `<button onclick="playPreview('${escapeQuotes(item.previewUrl)}','${escapeQuotes(item.trackName||item.collectionName||'')}','${escapeQuotes(item.artistName||'')}')">▶</button>` : ''}
          <button onclick="toggleFavorite('${item.trackId}')">❤️</button>
          <button onclick="removeFromLib('${item.trackId}')">🗑</button>
        </div>
      </div>
    `;
  }).join('');

  attachStarHandlers();
}

async function saveToLib(item){
  // salva/atualiza biblioteca
  await api('/library','POST', item);
  alert('Salvo na biblioteca!');
  await refreshAll();
}

async function removeFromLib(trackId){
  await api('/library','DELETE',{trackId});
  await refreshAll();
}

// ================== Favoritos ==================
async function fetchFavorites(){
  const r = await api('/favorites','GET');
  if(r.error) return [];
  return r;
}

async function toggleFavorite(trackId){
  await api('/favorites','POST',{trackId});
  await renderFavorites();
}

async function renderFavorites(){
  const favs = await fetchFavorites();
  if(!favs.length){
    favoritesDiv.innerHTML = '<p class="small">Nenhum favorito ainda. Use ❤️</p>';
    return;
  }
  favoritesDiv.innerHTML = favs.map(item => `
    <div class="track">
      <img class="thumb" src="${item.artworkUrl100||''}" onerror="this.style.display='none'"/>
      <div class="meta" style="flex:1">
        <div style="font-weight:600">${escapeHtml(item.trackName||item.collectionName||'—')}</div>
        <div class="small">${escapeHtml(item.artistName||'')}</div>
        <div class="small">Nota: ${item.rating || '—'}/5</div>
        <a class="small" style="color:#9fb0c8;text-decoration:underline"
           href="/album/${encodeURIComponent(item.trackId)}" target="_blank">
           Ver página →
        </a>
      </div>
      <div class="actions" style="gap:4px">
        ${item.previewUrl ? `<button onclick="playPreview('${escapeQuotes(item.previewUrl)}','${escapeQuotes(item.trackName||item.collectionName||'')}','${escapeQuotes(item.artistName||'')}')">▶</button>` : ''}
        <button onclick="toggleFavorite('${item.trackId}')">💔</button>
      </div>
    </div>
  `).join('');
}

// ================== Recentes ==================
async function renderRecent(){
  const arr = await api('/recent','GET');
  if(arr.error){
    recentDiv.innerHTML = '<p class="small">'+escapeHtml(arr.error)+'</p>';
    return;
  }
  if(!arr.length){
    recentDiv.innerHTML = '<p class="small">Nenhuma escuta registrada.</p>';
    return;
  }
  recentDiv.innerHTML = arr.slice(0,8).map(r => `
    <div class="small">${escapeHtml(r.name)} — ${new Date(r.playedAt).toLocaleString()}</div>
  `).join('');
}


function renderResults(items){
  if(!items.length){
    resultsDiv.innerHTML = '<p class="small">Nenhum resultado.</p>';
    return;
  }

  resultsDiv.innerHTML = items.map(it=>{
    const dataLean = lean(it);
    const trackId = dataLean.trackId;
    const art = dataLean.artworkUrl100 || '';
    const title = dataLean.trackName || '—';
    const artist= dataLean.artistName || '';
    const album = dataLean.collectionName || '';
    const preview = dataLean.previewUrl || '';

    return `
      <div class="track" style="align-items:flex-start;">
        <img class="thumb"
             src="${art}"
             onerror="this.style.display='none'"/>
        <div class="meta" style="flex:1">
          <div style="font-weight:600">${escapeHtml(title)}</div>
          <div class="small">${escapeHtml(artist)}${album? ' • '+escapeHtml(album):''}</div>
          <div class="small" style="margin-top:4px">
            <a style="color:#9fb0c8;text-decoration:underline"
               href="/album/${encodeURIComponent(trackId)}"
               target="_blank">Ver página do álbum/música →</a>
          </div>
        </div>
        <div class="actions" style="gap:4px">
          ${preview? `<button onclick="playPreview('${escapeQuotes(preview)}','${escapeQuotes(title)}','${escapeQuotes(artist)}')">▶</button>` : ''}
          <button onclick='saveToLib(${JSON.stringify(dataLean).replace(/</g,"\\u003c")})'>💾</button>
          <button onclick='toggleFavorite("${trackId}")'>❤️</button>
          <button onclick='showLyrics("${escapeQuotes(artist)}","${escapeQuotes(title)}")'>Letras</button>
        </div>
      </div>
    `;
  }).join('');
}


btnSearch.addEventListener('click', async ()=>{
  const q = qInput.value.trim();
  const ent = entitySelect.value;
  if(!q){ alert('Digite algo pra buscar.'); return; }
  resultsDiv.innerHTML = '<p class="small">Buscando...</p>';
  try{
    const items = await itunesSearch(q, ent);
    renderResults(items);
  }catch(e){
    resultsDiv.innerHTML = '<p class="small">Erro: '+escapeHtml(String(e))+'</p>';
  }
});

qInput.addEventListener('keypress', (e)=>{
  if(e.key==='Enter') btnSearch.click();
});


async function refreshAll(){
  await renderLibrary();
  await renderFavorites();
  await renderRecent();
}


(async function start(){
  await enterApp();
})();
