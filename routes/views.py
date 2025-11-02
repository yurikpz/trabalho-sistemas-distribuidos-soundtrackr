from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from models import get_db
import requests

bp = Blueprint('views', __name__)

#HELPERS
def current_user_id():
    return session.get('user_id')

def current_username():
    return session.get('username')

def get_current_user_full():
    uid = current_user_id()
    if not uid:
        return None
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, fandom, avatar, bio FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

#LANDING
@bp.route('/landing')
def landing():
    if not current_user_id():
        return redirect(url_for('auth.login'))

    user = get_current_user_full()

    query = "IVE"
    url = f"https://itunes.apple.com/search?term={query}&media=music&limit=12"
    resp = requests.get(url)
    data = resp.json().get('results', []) if resp.status_code == 200 else []

    return render_template('landing.html', logged_user=user, recommendations=data)


#BUSCAR
@bp.route('/search', methods=['GET'])
def search():
    term = request.args.get('term', '')
    entity = request.args.get('entity', 'musicTrack')  # track ou album
    url = f"https://itunes.apple.com/search?term={term}&entity={entity}&limit=20"
    resp = requests.get(url)
    if resp.status_code != 200:
        return jsonify([])
    return jsonify(resp.json().get('results', []))



#PÁGINA DO ÁLBUM/FAIXA

@bp.route('/album/<trackId>')
def album_page(trackId):
    uid = current_user_id()
    if not uid:
        return redirect(url_for('auth.login'))

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM library WHERE user_id=? AND trackId=?", (uid, trackId))
    album = c.fetchone()
    conn.close()

    # SE EXISTE NO BANCO - ROW - DICT
    if album is not None:
        album = dict(album)

    #SE NAÕ, BUSCA NA APPLE
    if not album:
        url = f"https://itunes.apple.com/lookup?id={trackId}"
        r = requests.get(url)
        if r.status_code == 200:
            js = r.json().get("results", [])
            album = js[0] if js else {}

    if not album:
        return "Música/Álbum não encontrado", 404

    artist = album.get("artistName", "")
    title = album.get("trackName") or album.get("collectionName", "")
    search_term = f"{artist} {title}"

    #BUSCAR MV E LETRA
    YT_KEY = "AIzaSyCwxWyijyzesFj1geR7m3S1T6j2X7BzJSU"
    def yt(q):
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&type=video&maxResults=1&videoEmbeddable=true"
            f"&q={requests.utils.quote(q)}&key={YT_KEY}"
        )
        if r.status_code != 200: return None
        items = r.json().get("items", [])
        return items[0]["id"]["videoId"] if items else None

    videoId = yt(search_term + " official mv") or yt(search_term + " lyric video")

    #SE EXISTIR, PEGAR NOTA DO USUÁRIO
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT rating FROM library WHERE user_id=? AND trackId=?", (uid, trackId))
    r = c.fetchone()
    conn.close()
    user_rating = r['rating'] if r else 0

    return render_template(
        'album.html',
        album=album,
        videoId=videoId,
        username=current_username(),
        user_rating=user_rating
    )



#PERFIL

@bp.route('/perfil')
def perfil():
    uid = current_user_id()
    if not uid:
        return redirect(url_for('auth.login'))

    user = get_current_user_full()

    conn = get_db()
    c = conn.cursor()

    #FAVORITOS
    c.execute("""
        SELECT * FROM favorites
        WHERE user_id=? ORDER BY id DESC
    """, (uid,))
    favorites = [dict(r) for r in c.fetchall()]

    #OUVIDAS
    c.execute("""
        SELECT * FROM listened
        WHERE user_id=? ORDER BY id DESC LIMIT 50
    """, (uid,))
    ouvidas = [dict(r) for r in c.fetchall()]

    #LISTAS+CAPAS
    c.execute("SELECT * FROM lists WHERE user_id=? ORDER BY createdAt DESC", (uid,))
    listas = [dict(r) for r in c.fetchall()]

    for l in listas:
        c.execute("SELECT artworkUrl100 FROM list_items WHERE list_id=? ORDER BY addedAt DESC LIMIT 1", (l['id'],))
        img = c.fetchone()
        l['cover'] = img['artworkUrl100'] if img else None

    conn.close()

    return render_template('perfil.html', user=user, favorites=favorites, ouvidas=ouvidas, listas=listas)



#PAGINA DE UMA LISTA

@bp.route('/lista/<int:list_id>')
def view_list(list_id):
    uid = current_user_id()  #PODE ESTAR LOGADO OU NÃO

    conn = get_db()
    c = conn.cursor()

    #BUSCAR LISTA E DONO
    c.execute("""
        SELECT l.*, u.username, u.avatar
        FROM lists l
        JOIN users u ON u.id = l.user_id
        WHERE l.id = ?
    """, (list_id,))
    lista = c.fetchone()

    if not lista:
        return "Lista não encontrada", 404

    lista = dict(lista)

    #BUSCAR ITENS
    c.execute("""
        SELECT *
        FROM list_items
        WHERE list_id = ?
        ORDER BY addedAt DESC
    """, (list_id,))
    items = [dict(r) for r in c.fetchall()]
    conn.close()

    #CONFERIR SE QUEM TA VISITANDO O PERFIL NÃO É O DONO DA LISTA
    is_owner = uid == lista["user_id"]

    return render_template(
        "lista.html",
        lista=lista,
        items=items,
        is_owner=is_owner,
        public_view=not is_owner
    )




# DIÁRIO

@bp.route('/diary')
def diary():
    uid = current_user_id()
    if not uid:
        return redirect(url_for('auth.login'))

    user = get_current_user_full()

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM diary
        WHERE user_id=?
        ORDER BY listenedAt DESC
    """, (uid,))
    diary = [dict(r) for r in c.fetchall()]
    conn.close()

    return render_template("diary.html", user=user, diary=diary)



#REDIRECIONAMENTO HOME

@bp.route('/')
def index():
    if current_user_id():
        return redirect(url_for('views.landing'))
    return redirect(url_for('auth.login'))

#PÁGINA DO ARTISTA (WIKI)

@bp.route('/artist/<name>')
def artist_page(name):
    import requests, urllib.parse

    def safe_json(url):
        try:
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            return r.json()
        except:
            return {}

    #BUSCA TITULO EM PORTUGUÊS
    def wiki_search(lang, query):
        url = (
            f"https://{lang}.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={urllib.parse.quote(query)}"
            "&srlimit=1&format=json&utf8=1"
        )
        data = safe_json(url)
        results = data.get("query", {}).get("search", [])
        return results[0]["title"] if results else None

    #BUSCAR BIO E FOTO
    def wiki_extract(lang, title):
        url = (
            f"https://{lang}.wikipedia.org/w/api.php"
            "?action=query&prop=extracts|pageimages&explaintext&exintro&redirects=1"
            f"&piprop=thumbnail&pithumbsize=600&titles={urllib.parse.quote(title)}"
            "&format=json&utf8=1"
        )
        data = safe_json(url)
        pages = (data.get("query") or {}).get("pages") or {}
        if not pages: return None, None
        page = next(iter(pages.values()))
        text = page.get("extract")
        img = (page.get("thumbnail") or {}).get("source")
        return text, img

    # DETECTAR SE ESTÁ EM OUTRA LINGUA
    def wiki_pt_link(en_title):
        url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&prop=langlinks&lllang=pt&titles={urllib.parse.quote(en_title)}"
            "&format=json&utf8=1"
        )
        data = safe_json(url)
        pages = (data.get("query") or {}).get("pages") or {}
        page = next(iter(pages.values()))
        links = page.get("langlinks") or []
        for l in links:
            if l.get("lang") == "pt":
                return l.get("*")
        return None

    #TENTATIVA DE ACHAR O ARTISTA PELO NOME
    queries = [
        name,
        f"{name} (musician)",
        f"{name} (rapper)",
        f"{name} singer",
        f"{name} group",
        f"{name} band",
        f"{name} k-pop",
    ]

    bio = None
    img = None

    #TENTA EM PORTUGUES
    for q in queries:
        pt_title = wiki_search("pt", q)
        if pt_title:
            bio, img = wiki_extract("pt", pt_title)
            if bio: break

    #SE NÃO TIVER EM PT, BUSCA EM INGLÊS E TRADUZ
    if not bio:
        for q in queries:
            en_title = wiki_search("en", q)
            if not en_title: continue

            # se houver link pra página PT, usa ela
            pt_equivalent = wiki_pt_link(en_title)
            if pt_equivalent:
                bio, img = wiki_extract("pt", pt_equivalent)
                if bio: break

            # senão usa EN
            bio, img = wiki_extract("en", en_title)
            if bio:
                bio_lang = "en"
                break

    #TRADUZ A BIO DE INGLES PRA PORTUGUÊS
    translated = None
    if bio and "English Wikipedia" not in (bio or "") and bio.strip():
        if "bio_lang" in locals() and bio_lang == "en":
            try:
                t = requests.post(
                    "https://libretranslate.com/translate",
                    json={
                        "q": bio[:2000],
                        "source": "en",
                        "target": "pt"
                    },
                    timeout=5
                ).json()
                translated = t.get("translatedText")
            except:
                translated = None

    bio = translated or bio or "Biografia não encontrada 😢"

    # MUSICAS DO ARTISTA(PUXA DA API ITUNES)
    itunes_url = f"https://itunes.apple.com/search?term={urllib.parse.quote(name)}&entity=musicTrack&limit=24"
    data = safe_json(itunes_url)
    tracks = [
        t for t in data.get("results", [])
        if t.get("trackName") and t.get("artistName")
    ]

    return render_template("artist.html", name=name, bio=bio, photo=img, tracks=tracks)

