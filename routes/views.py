from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from models import get_db
import psycopg2.extras
import requests
import logging
import random
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

    recommendations = _get_recommendations(uid)

    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT following_id FROM follows WHERE follower_id=%s", (uid,))
    following_ids = [r['following_id'] for r in c.fetchall()]

    # ── Sua Semana (últimos 7 dias, dados da própria plataforma) ─────────────
    c.execute("""
        SELECT "artistName", COUNT(*) AS cnt
        FROM library
        WHERE user_id=%s AND rating > 0
          AND "addedAt"::timestamp >= NOW() - INTERVAL '7 days'
        GROUP BY "artistName"
        ORDER BY cnt DESC
        LIMIT 3
    """, (uid,))
    week_top_artists = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT "trackId", "trackName", "artistName", "artworkUrl100", rating
        FROM library
        WHERE user_id=%s AND rating > 0
          AND "addedAt"::timestamp >= NOW() - INTERVAL '7 days'
        ORDER BY "addedAt" DESC
        LIMIT 5
    """, (uid,))
    week_top_tracks = [dict(r) for r in c.fetchall()]

    # ── Mini ranking (top 5 mais avaliadas da plataforma) ─────────────────────
    c.execute("""
        SELECT
            "trackId", "trackName", "artistName", "artworkUrl100",
            COUNT(*) AS rating_count,
            ROUND(AVG(rating)::numeric, 1) AS avg_rating
        FROM library
        WHERE rating > 0
        GROUP BY "trackId", "trackName", "artistName", "artworkUrl100"
        ORDER BY rating_count DESC, avg_rating DESC
        LIMIT 5
    """)
    ranking_preview = [dict(r) for r in c.fetchall()]
    for item in ranking_preview:
        item['avg_rating'] = float(item['avg_rating'])

    conn.close()

    return render_template(
        'landing.html',
        logged_user=user,
        recommendations=recommendations,
        following_count=len(following_ids),
        week_top_artists=week_top_artists,
        week_top_tracks=week_top_tracks,
        ranking_preview=ranking_preview,
    )


def _get_recommendations(uid):
    """
    Monta recomendações personalizadas:
    1. Pega os top artistas avaliados/favoritados pelo usuário
    2. Busca artistas similares via Last.fm
    3. Traz músicas reais desses artistas via iTunes
    Se não houver histórico suficiente, cai no fallback de charts reais do iTunes.
    """
    import os
    LASTFM_KEY = os.environ.get("LASTFM_API_KEY")

    conn = get_db()
    c    = _cursor(conn)

    c.execute("""
        SELECT "artistName", COUNT(*) AS cnt
        FROM (
            SELECT "artistName" FROM library WHERE user_id=%s AND rating > 0
            UNION ALL
            SELECT "artistName" FROM favorites WHERE user_id=%s
        ) sub
        WHERE "artistName" IS NOT NULL AND "artistName" != ''
        GROUP BY "artistName"
        ORDER BY cnt DESC
        LIMIT 3
    """, (uid, uid))
    top_artists = [r['artistName'] for r in c.fetchall()]
    conn.close()

    tracks = []

    if top_artists and LASTFM_KEY:
        similar_artists = set()

        for artist in top_artists:
            try:
                r = requests.get(
                    "https://ws.audioscrobbler.com/2.0/",
                    params={
                        "method": "artist.getsimilar",
                        "artist": artist,
                        "api_key": LASTFM_KEY,
                        "format": "json",
                        "limit": 4
                    },
                    timeout=5
                )
                data = r.json()
                names = [a['name'] for a in data.get('similarartists', {}).get('artist', [])]
                similar_artists.update(names[:4])
            except Exception as e:
                logger.warning("Last.fm falhou para %s: %s", artist, e)

        for artist_name in list(similar_artists)[:8]:
            try:
                r = requests.get(
                    "https://itunes.apple.com/search",
                    params={"term": artist_name, "entity": "musicTrack", "limit": 2},
                    timeout=5
                )
                if r.status_code == 200:
                    tracks += r.json().get('results', [])
            except Exception as e:
                logger.warning("iTunes falhou para %s: %s", artist_name, e)

    if len(tracks) < 8:
        try:
            r = requests.get(
                "https://itunes.apple.com/us/rss/topsongs/limit=15/json",
                timeout=5
            )
            if r.status_code == 200:
                entries = r.json().get('feed', {}).get('entry', [])
                for e in entries:
                    tracks.append({
                        'trackId': e.get('id', {}).get('attributes', {}).get('im:id'),
                        'trackName': e.get('im:name', {}).get('label'),
                        'artistName': e.get('im:artist', {}).get('label'),
                        'artworkUrl100': e.get('im:image', [{}, {}, {}])[2].get('label') if e.get('im:image') else None,
                    })
        except Exception as e:
            logger.warning("iTunes RSS falhou: %s", e)

    seen = set()
    unique_tracks = []
    for t in tracks:
        tid = t.get('trackId')
        if tid and tid not in seen:
            seen.add(tid)
            unique_tracks.append(t)

    return unique_tracks[:15]


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

    c.execute("""
        SELECT user_id, username, avatar,
               "trackId", "trackName", "artistName", "artworkUrl100",
               date, type, rating, review_text
        FROM (
            SELECT
                u.id AS user_id, u.username, u.avatar,
                l."trackId", l."trackName", l."artistName", l."artworkUrl100",
                l."listenedAt"::text AS date, 'listened' AS type,
                NULL::int AS rating, NULL::text AS review_text
            FROM listened l JOIN users u ON u.id = l.user_id
            WHERE l.user_id = ANY(%s)

            UNION ALL

            SELECT
                u.id, u.username, u.avatar,
                lb."trackId", lb."trackName", lb."artistName", lb."artworkUrl100",
                lb."addedAt"::text, 'rated', lb.rating, NULL::text
            FROM library lb JOIN users u ON u.id = lb.user_id
            WHERE lb.user_id = ANY(%s) AND lb.rating > 0

            UNION ALL

            SELECT
                u.id, u.username, u.avatar,
                r."trackId",
                COALESCE(l2."trackName", ''),
                COALESCE(l2."artistName", ''),
                COALESCE(l2."artworkUrl100", ''),
                r."createdAt"::text, 'review', NULL::int, r.text
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


# ── Preview de áudio ──────────────────────────────────────────────────────────

@bp.route('/preview/<trackId>')
def preview_url(trackId):
    try:
        r = requests.get(
            "https://itunes.apple.com/lookup",
            params={"id": trackId},
            timeout=5
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                return jsonify({'previewUrl': results[0].get('previewUrl')})
    except Exception as e:
        logger.error("Erro preview lookup: %s", e)
    return jsonify({'previewUrl': None})

#-----Roleta----@bp.route('/roulette')
def roulette_api():
    if not current_user_id():
        return jsonify({'error': 'not_logged_in'}), 401

    mode    = request.args.get('mode', 'random')
    country = request.args.get('country', '')

    countries = ['us', 'br', 'gb', 'jp', 'kr', 'de', 'fr', 'es', 'it', 'ca', 'au', 'mx']

    if mode == 'taste':
        uid  = current_user_id()
        conn = get_db()
        c    = _cursor(conn)
        c.execute("""
            SELECT "artistName" FROM (
                SELECT "artistName" FROM library WHERE user_id=%s AND rating > 0
                UNION ALL
                SELECT "artistName" FROM favorites WHERE user_id=%s
            ) sub WHERE "artistName" IS NOT NULL AND "artistName" != ''
            GROUP BY "artistName" ORDER BY COUNT(*) DESC LIMIT 5
        """, (uid, uid))
        top_artists = [r['artistName'] for r in c.fetchall()]
        conn.close()

        if not top_artists:
            return jsonify({'error': 'no_taste_data'}), 400

        seed_artist   = random.choice(top_artists)
        chosen_artist = seed_artist

        import os
        LASTFM_KEY = os.environ.get("LASTFM_API_KEY")
        if LASTFM_KEY:
            try:
                r = requests.get(
                    "https://ws.audioscrobbler.com/2.0/",
                    params={
                        "method": "artist.getsimilar", "artist": seed_artist,
                        "api_key": LASTFM_KEY, "format": "json", "limit": 10
                    },
                    timeout=5
                )
                data = r.json()
                similar = [a['name'] for a in data.get('similarartists', {}).get('artist', [])]
                if similar:
                    chosen_artist = random.choice(similar)
            except Exception as e:
                logger.warning("Last.fm falhou na roleta: %s", e)

        try:
            r = requests.get(
                "https://itunes.apple.com/search",
                params={"term": chosen_artist, "entity": "musicTrack", "limit": 25},
                timeout=5
            )
            results = r.json().get('results', []) if r.status_code == 200 else []
        except Exception:
            results = []

        if not results:
            return jsonify({'error': 'no_results'}), 404

        track = random.choice(results)
        return jsonify({'track': track, 'based_on': seed_artist})

    else:
        country_code = country if country in countries else random.choice(countries)
        try:
            r = requests.get(
                f"https://itunes.apple.com/{country_code}/rss/topsongs/limit=50/json",
                timeout=6
            )
            entries = r.json().get('feed', {}).get('entry', []) if r.status_code == 200 else []
        except Exception:
            entries = []

        if not entries:
            return jsonify({'error': 'no_results'}), 404

        e = random.choice(entries)
        track = {
            'trackId':       e.get('id', {}).get('attributes', {}).get('im:id'),
            'trackName':     e.get('im:name', {}).get('label'),
            'artistName':    e.get('im:artist', {}).get('label'),
            'artworkUrl100': e.get('im:image', [{}, {}, {}])[2].get('label') if e.get('im:image') else None,
        }
        return jsonify({'track': track, 'country': country_code})
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
    is_owner = uid == lista["user_id"]

    if not lista.get("is_public", 1) and not is_owner:
        conn.close()
        return "Esta lista é privada", 403

    c.execute('SELECT * FROM list_items WHERE list_id=%s ORDER BY "addedAt" DESC', (list_id,))
    items = [dict(r) for r in c.fetchall()]

    if not lista.get("cover") and items:
        lista["auto_cover"] = items[0].get("artworkUrl100")

    c.execute("SELECT COUNT(*) AS cnt FROM list_likes WHERE list_id=%s", (list_id,))
    likes_count = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) AS cnt FROM list_saves WHERE list_id=%s", (list_id,))
    saves_count = c.fetchone()["cnt"]

    liked_by_me = saved_by_me = False
    if uid:
        c.execute("SELECT 1 FROM list_likes WHERE user_id=%s AND list_id=%s", (uid, list_id))
        liked_by_me = c.fetchone() is not None
        c.execute("SELECT 1 FROM list_saves WHERE user_id=%s AND list_id=%s", (uid, list_id))
        saved_by_me = c.fetchone() is not None

    conn.close()

    return render_template(
        "lista.html",
        lista=lista,
        items=items,
        is_owner=is_owner,
        public_view=not is_owner,
        likes_count=likes_count,
        saves_count=saves_count,
        liked_by_me=liked_by_me,
        saved_by_me=saved_by_me,
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

# Semaninha
@bp.route('/semaninha')
def semaninha_page():
    if not current_user_id():
        return redirect(url_for('auth.login'))
    return render_template('collage.html')
# ── Ranking ───────────────────────────────────────────────────────────────────

@bp.route('/ranking')
def ranking():
    if not current_user_id():
        return redirect(url_for('auth.login'))

    conn = get_db()
    c    = _cursor(conn)

    # Mais avaliadas (por volume de avaliações)
    c.execute("""
        SELECT
            "trackId", "trackName", "artistName", "artworkUrl100",
            COUNT(*) AS rating_count,
            ROUND(AVG(rating)::numeric, 1) AS avg_rating
        FROM library
        WHERE rating > 0
        GROUP BY "trackId", "trackName", "artistName", "artworkUrl100"
        ORDER BY rating_count DESC, avg_rating DESC
        LIMIT 30
    """)
    most_rated = [dict(r) for r in c.fetchall()]

    # Melhor avaliadas (nota média, com mínimo de 2 votos pra evitar distorção)
    c.execute("""
        SELECT
            "trackId", "trackName", "artistName", "artworkUrl100",
            COUNT(*) AS rating_count,
            ROUND(AVG(rating)::numeric, 1) AS avg_rating
        FROM library
        WHERE rating > 0
        GROUP BY "trackId", "trackName", "artistName", "artworkUrl100"
        HAVING COUNT(*) >= 2
        ORDER BY avg_rating DESC, rating_count DESC
        LIMIT 30
    """)
    top_rated = [dict(r) for r in c.fetchall()]

    conn.close()

    for item in most_rated + top_rated:
        item['avg_rating'] = float(item['avg_rating'])

    return render_template('ranking.html', most_rated=most_rated, top_rated=top_rated)