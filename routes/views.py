from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from models import get_db
import psycopg2.extras
import requests
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('views', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def current_user_id():
    return session.get('user_id')

def current_username():
    return session.get('username')

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def get_current_user_full():
    uid = current_user_id()
    if not uid:
        return None
    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT id, username, fandom, avatar, bio FROM users WHERE id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ── Raiz ──────────────────────────────────────────────────────────────────────

@bp.route('/')
def index():
    if current_user_id():
        return redirect(url_for('views.landing'))
    return redirect(url_for('auth.login'))


# ── Landing ───────────────────────────────────────────────────────────────────

@bp.route('/landing')
def landing():
    if not current_user_id():
        return redirect(url_for('auth.login'))

    uid  = current_user_id()
    user = get_current_user_full()

    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={"term": "top hits 2024", "media": "music", "limit": 12},
            timeout=5
        )
        recommendations = resp.json().get('results', []) if resp.status_code == 200 else []
    except Exception:
        recommendations = []

    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT following_id FROM follows WHERE follower_id=%s", (uid,))
    following_ids = [r['following_id'] for r in c.fetchall()]
    conn.close()

    return render_template(
        'landing.html',
        logged_user=user,
        recommendations=recommendations,
        following_count=len(following_ids)
    )


# ── Feed paginado (API) ───────────────────────────────────────────────────────

@bp.route('/feed')
def feed_api():
    uid = current_user_id()
    if not uid:
        return jsonify([])

    page     = int(request.args.get('page', 0))
    per_page = 20
    offset   = page * per_page

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT following_id FROM follows WHERE follower_id=%s", (uid,))
    following_ids = [r['following_id'] for r in c.fetchall()]

    if not following_ids:
        conn.close()
        return jsonify([])

    # PostgreSQL usa ANY(%s) com lista em vez de IN (?,?,?)
    c.execute("""
        SELECT user_id, username, avatar,
               "trackId", "trackName", "artistName", "artworkUrl100",
               date, type, rating, review_text
        FROM (
            SELECT
                u.id AS user_id, u.username, u.avatar,
                l."trackId", l."trackName", l."artistName", l."artworkUrl100",
                l."listenedAt" AS date, 'listened' AS type,
                NULL::int AS rating, NULL::text AS review_text
            FROM listened l JOIN users u ON u.id = l.user_id
            WHERE l.user_id = ANY(%s)

            UNION ALL

            SELECT
                u.id, u.username, u.avatar,
                lb."trackId", lb."trackName", lb."artistName", lb."artworkUrl100",
                lb."addedAt", 'rated', lb.rating, NULL::text
            FROM library lb JOIN users u ON u.id = lb.user_id
            WHERE lb.user_id = ANY(%s) AND lb.rating > 0

            UNION ALL

            SELECT
                u.id, u.username, u.avatar,
                r."trackId",
                COALESCE(l2."trackName", ''),
                COALESCE(l2."artistName", ''),
                COALESCE(l2."artworkUrl100", ''),
                r."createdAt", 'review', NULL::int, r.text
            FROM reviews r JOIN users u ON u.id = r.user_id
            LEFT JOIN library l2 ON l2."trackId" = r."trackId" AND l2.user_id = r.user_id
            WHERE r.user_id = ANY(%s)

            UNION ALL

            SELECT
                u.id, u.username, u.avatar,
                f."trackId", f."trackName", f."artistName", f."artworkUrl100",
                ''::text, 'favorited', NULL::int, NULL::text
            FROM favorites f JOIN users u ON u.id = f.user_id
            WHERE f.user_id = ANY(%s)
        ) sub
        ORDER BY date DESC
        LIMIT %s OFFSET %s
    """, (following_ids, following_ids, following_ids, following_ids, per_page, offset))

    feed = [dict(r) for r in c.fetchall()]
    conn.close()

    for item in feed:
        item['avatar'] = item.get('avatar') or 'img/default.png'

    return jsonify(feed)


# ── Busca (JSON) ──────────────────────────────────────────────────────────────

@bp.route('/search', methods=['GET'])
def search():
    term   = request.args.get('term', '').strip()
    entity = request.args.get('entity', 'musicTrack')
    if not term:
        return jsonify([])
    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={"term": term, "entity": entity, "limit": 20},
            timeout=5
        )
        if resp.status_code != 200:
            return jsonify([])
        return jsonify(resp.json().get('results', []))
    except Exception as e:
        logger.error("Erro na busca iTunes: %s", e)
        return jsonify([])


# ── YouTube helper ────────────────────────────────────────────────────────────

def _youtube_search(query):
    import os
    YT_KEY = os.environ.get("YOUTUBE_API_KEY")
    if not YT_KEY:
        return None
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet", "type": "video",
                "videoEmbeddable": "true", "maxResults": 1,
                "q": query, "key": YT_KEY,
            },
            timeout=5
        )
        if r.status_code != 200:
            return None
        items = r.json().get("items", [])
        return items[0]["id"]["videoId"] if items else None
    except Exception as e:
        logger.error("Erro YouTube: %s", e)
        return None


# ── Página de álbum / faixa ───────────────────────────────────────────────────

@bp.route('/album/<trackId>')
def album_page(trackId):
    uid = current_user_id()
    if not uid:
        return redirect(url_for('auth.login'))

    conn = get_db()
    c    = _cursor(conn)
    c.execute('SELECT * FROM library WHERE user_id=%s AND "trackId"=%s', (uid, trackId))
    album = c.fetchone()
    conn.close()

    album = dict(album) if album else None

    if not album:
        try:
            r = requests.get(
                "https://itunes.apple.com/lookup",
                params={"id": trackId},
                timeout=5
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                album = results[0] if results else {}
        except Exception as e:
            logger.error("Erro iTunes lookup: %s", e)
            album = {}

    if not album:
        return "Música/Álbum não encontrado", 404

    artist = album.get("artistName", "")
    title  = album.get("trackName") or album.get("collectionName", "")

    videoId = _youtube_search(f"{artist} {title} official mv") \
           or _youtube_search(f"{artist} {title} lyric video")

    conn = get_db()
    c    = _cursor(conn)
    c.execute('SELECT rating FROM library WHERE user_id=%s AND "trackId"=%s', (uid, trackId))
    row = c.fetchone()
    conn.close()
    user_rating = row['rating'] if row else 0

    return render_template(
        'album.html',
        album=album,
        videoId=videoId,
        username=current_username(),
        user_rating=user_rating
    )


# ── Página de lista ───────────────────────────────────────────────────────────

@bp.route('/lista/<int:list_id>')
def view_list(list_id):
    uid = current_user_id()

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT l.*, u.username, u.avatar
        FROM lists l JOIN users u ON u.id = l.user_id
        WHERE l.id = %s
    """, (list_id,))
    lista = c.fetchone()

    if not lista:
        conn.close()
        return "Lista não encontrada", 404

    lista = dict(lista)
    c.execute('SELECT * FROM list_items WHERE list_id=%s ORDER BY "addedAt" DESC', (list_id,))
    items = [dict(r) for r in c.fetchall()]
    conn.close()

    is_owner = uid == lista["user_id"]
    return render_template(
        "lista.html",
        lista=lista,
        items=items,
        is_owner=is_owner,
        public_view=not is_owner
    )


# ── Página de artista ─────────────────────────────────────────────────────────

@bp.route('/artist/<name>')
def artist_page(name):

    def safe_json(url, params=None):
        try:
            r = requests.get(url, params=params, timeout=5,
                             headers={"User-Agent": "Mozilla/5.0"})
            return r.json()
        except Exception as e:
            logger.warning("safe_json falhou %s: %s", url, e)
            return {}

    def wiki_search(lang, query):
        data = safe_json(f"https://{lang}.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search",
            "srsearch": query, "srlimit": 1,
            "format": "json", "utf8": 1
        })
        results = data.get("query", {}).get("search", [])
        return results[0]["title"] if results else None

    def wiki_extract(lang, title):
        data = safe_json(f"https://{lang}.wikipedia.org/w/api.php", params={
            "action": "query", "prop": "extracts|pageimages",
            "explaintext": True, "exintro": True, "redirects": 1,
            "piprop": "thumbnail", "pithumbsize": 600,
            "titles": title, "format": "json", "utf8": 1
        })
        pages = (data.get("query") or {}).get("pages") or {}
        if not pages:
            return None, None
        page = next(iter(pages.values()))
        return page.get("extract"), (page.get("thumbnail") or {}).get("source")

    def wiki_pt_link(en_title):
        data = safe_json("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "prop": "langlinks",
            "lllang": "pt", "titles": en_title,
            "format": "json", "utf8": 1
        })
        pages = (data.get("query") or {}).get("pages") or {}
        page  = next(iter(pages.values()))
        for link in page.get("langlinks") or []:
            if link.get("lang") == "pt":
                return link.get("*")
        return None

    queries = [
        name, f"{name} (musician)", f"{name} (rapper)",
        f"{name} singer", f"{name} group",
        f"{name} band",   f"{name} k-pop",
    ]

    bio = img = None
    bio_lang  = "pt"

    for q in queries:
        pt_title = wiki_search("pt", q)
        if pt_title:
            bio, img = wiki_extract("pt", pt_title)
            if bio:
                break

    if not bio:
        for q in queries:
            en_title = wiki_search("en", q)
            if not en_title:
                continue
            pt_equiv = wiki_pt_link(en_title)
            if pt_equiv:
                bio, img = wiki_extract("pt", pt_equiv)
                if bio:
                    break
            bio, img = wiki_extract("en", en_title)
            if bio:
                bio_lang = "en"
                break

    if bio and bio_lang == "en":
        try:
            t = requests.post(
                "https://libretranslate.com/translate",
                json={"q": bio[:2000], "source": "en", "target": "pt"},
                timeout=5
            ).json()
            bio = t.get("translatedText") or bio
        except Exception:
            pass

    bio = bio or "Biografia não encontrada"

    itunes = safe_json("https://itunes.apple.com/search", params={
        "term": name, "entity": "musicTrack", "limit": 24
    })
    tracks = [
        t for t in itunes.get("results", [])
        if t.get("trackName") and t.get("artistName")
    ]

    return render_template("artist.html", name=name, bio=bio, photo=img, tracks=tracks)


# ── Coleção ───────────────────────────────────────────────────────────────────

@bp.route('/colecao')
def collection_page():
    uid = current_user_id()
    if not uid:
        return redirect(url_for('auth.login'))
    user = get_current_user_full()
    return render_template('collection.html', user=user, user_id=uid)