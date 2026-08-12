from flask import Blueprint, request, jsonify, session
from models import get_db
import psycopg2.extras
import requests
import os

bp = Blueprint('lastfm', __name__)

LASTFM_KEY = os.environ.get("LASTFM_API_KEY")
LASTFM_API = "https://ws.audioscrobbler.com/2.0/"

VALID_PERIODS = {'7day', '1month', '3month', '6month', '12month', 'overall'}


def current_user_id():
    return session.get('user_id')

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def _lastfm_get(method, **params):
    params.update({'method': method, 'api_key': LASTFM_KEY, 'format': 'json'})
    try:
        r = requests.get(LASTFM_API, params=params, timeout=6)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


# ── Conectar conta Last.fm ─────────────────────────────────────────────────────

@bp.route('/lastfm/connect', methods=['POST'])
def connect_lastfm():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    data     = request.get_json(force=True)
    username = (data.get('username') or '').strip()

    if not username:
        return jsonify({'error': 'missing_username'}), 400

    # Valida que o usuário existe no Last.fm
    check = _lastfm_get('user.getinfo', user=username)
    if not check or 'user' not in check:
        return jsonify({'error': 'user_not_found'}), 404

    conn = get_db()
    c    = _cursor(conn)
    c.execute("UPDATE users SET lastfm_username=%s WHERE id=%s", (username, uid))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'username': username})


@bp.route('/lastfm/disconnect', methods=['POST'])
def disconnect_lastfm():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)
    c.execute("UPDATE users SET lastfm_username=NULL WHERE id=%s", (uid,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


# ── Dados pra collage / semaninha ──────────────────────────────────────────────

@bp.route('/lastfm/collage_data')
def collage_data():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT lastfm_username FROM users WHERE id=%s", (uid,))
    row = c.fetchone()
    conn.close()

    username = (row or {}).get('lastfm_username')
    if not username:
        return jsonify({'error': 'not_connected'}), 400

    period = request.args.get('period', '7day')
    ctype  = request.args.get('type', 'album')  # 'album' ou 'artist'
    limit  = int(request.args.get('limit', 25))

    if period not in VALID_PERIODS:
        period = '7day'

    if ctype == 'artist':
        data = _lastfm_get('user.gettopartists', user=username, period=period, limit=limit)
        items = (data or {}).get('topartists', {}).get('artist', [])
        results = [{
            'name': a.get('name'),
            'sub': f"{a.get('playcount', '0')} plays",
            'image': next((img.get('#text') for img in a.get('image', []) if img.get('size') == 'extralarge'), None),
        } for a in items]
    else:
        data = _lastfm_get('user.gettopalbums', user=username, period=period, limit=limit)
        items = (data or {}).get('topalbums', {}).get('album', [])
        results = [{
            'name': a.get('name'),
            'sub': a.get('artist', {}).get('name', ''),
            'image': next((img.get('#text') for img in a.get('image', []) if img.get('size') == 'extralarge'), None),
        } for a in items]

    return jsonify({'items': results, 'username': username})


# ── Resumo semanal (pra sidebar da landing) ────────────────────────────────────

@bp.route('/lastfm/week_summary')
def week_summary():
    uid = current_user_id()
    if not uid:
        return jsonify({'connected': False})

    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT lastfm_username FROM users WHERE id=%s", (uid,))
    row = c.fetchone()
    conn.close()

    username = (row or {}).get('lastfm_username')
    if not username:
        return jsonify({'connected': False})

    artists_data = _lastfm_get('user.gettopartists', user=username, period='7day', limit=3)
    albums_data  = _lastfm_get('user.gettopalbums', user=username, period='7day', limit=3)

    top_artists = [{
        'name': a.get('name'),
        'playcount': a.get('playcount'),
    } for a in (artists_data or {}).get('topartists', {}).get('artist', [])]

    top_albums = [{
        'name': a.get('name'),
        'artist': a.get('artist', {}).get('name', ''),
        'image': next((img.get('#text') for img in a.get('image', []) if img.get('size') == 'large'), None),
        'playcount': a.get('playcount'),
    } for a in (albums_data or {}).get('topalbums', {}).get('album', [])]

    # Gêneros aproximados via tags do artista #1
    genres = []
    if top_artists:
        tags_data = _lastfm_get('artist.gettoptags', artist=top_artists[0]['name'])
        genres = [t.get('name') for t in (tags_data or {}).get('toptags', {}).get('tag', [])[:3]]

    return jsonify({
        'connected': True,
        'username': username,
        'top_artists': top_artists,
        'top_albums': top_albums,
        'genres': genres,
    })