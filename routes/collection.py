from flask import Blueprint, request, jsonify, session, current_app
from models import get_db
from datetime import datetime
import psycopg2.extras
import requests
import os

bp = Blueprint('collection', __name__)

ALLOWED_MEDIA  = {'Vinil', 'CD', 'Cassete', 'Outro'}
DISCOGS_TOKEN  = os.environ.get('DISCOGS_TOKEN')
DISCOGS_UA     = 'Soundtrackr/1.0'

def current_user_id():
    return session.get('user_id')

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Busca no Discogs (proxy) ───────────────────────────────────────────────────

@bp.route('/collection/discogs_search')
def discogs_search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])

    if not DISCOGS_TOKEN:
        return jsonify([])

    try:
        r = requests.get(
            'https://api.discogs.com/database/search',
            params={
                'q': q,
                'type': 'release',
                'per_page': 10,
                'token': DISCOGS_TOKEN,
            },
            headers={'User-Agent': DISCOGS_UA},
            timeout=6
        )
        if r.status_code != 200:
            return jsonify([])

        data = r.json()
        results = []
        for item in data.get('results', []):
            title_full = item.get('title', '')
            if ' - ' in title_full:
                artist, title = title_full.split(' - ', 1)
            else:
                artist, title = '', title_full

            formats = item.get('format') or []

            results.append({
                'discogs_id':    item.get('id'),
                'artistName':    artist.strip(),
                'trackName':     title.strip(),
                'artworkUrl100': item.get('cover_image') or item.get('thumb') or '',
                'year':          str(item.get('year') or ''),
                'label':         (item.get('label') or [''])[0],
                'catno':         item.get('catno', ''),
                'country':       item.get('country', ''),
                'format':        ', '.join(formats),
            })

        return jsonify(results)
    except Exception as e:
        print('Erro Discogs:', e)
        return jsonify([])


# ── Listar coleção ────────────────────────────────────────────────────────────

@bp.route('/collection/<int:user_id>')
def list_collection(user_id):
    uid = current_user_id()

    conn = get_db()
    c    = _cursor(conn)

    if uid != user_id:
        c.execute("""
            SELECT * FROM collection
            WHERE user_id=%s AND is_public=1
            ORDER BY "addedAt" DESC
        """, (user_id,))
    else:
        c.execute("""
            SELECT * FROM collection
            WHERE user_id=%s
            ORDER BY "addedAt" DESC
        """, (user_id,))

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)


# ── Adicionar item ────────────────────────────────────────────────────────────

@bp.route('/collection/add', methods=['POST'])
def add_to_collection():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    if request.content_type and 'multipart' in request.content_type:
        trackId       = request.form.get('trackId', '')
        trackName     = request.form.get('trackName', '')
        artistName    = request.form.get('artistName', '')
        artworkUrl100 = request.form.get('artworkUrl100', '')
        media_type    = request.form.get('media_type', '')
        is_public     = int(request.form.get('is_public', 1))
        discogs_id    = request.form.get('discogs_id', '')
        year          = request.form.get('year', '')
        label         = request.form.get('label', '')
        catno         = request.form.get('catno', '')
        country       = request.form.get('country', '')
        photo_file    = request.files.get('photo')
    else:
        data          = request.get_json(force=True)
        trackId       = data.get('trackId', '')
        trackName     = data.get('trackName', '')
        artistName    = data.get('artistName', '')
        artworkUrl100 = data.get('artworkUrl100', '')
        media_type    = data.get('media_type', '')
        is_public     = int(data.get('is_public', 1))
        discogs_id    = data.get('discogs_id', '')
        year          = data.get('year', '')
        label         = data.get('label', '')
        catno         = data.get('catno', '')
        country       = data.get('country', '')
        photo_file    = None

    if not trackName or not media_type:
        return jsonify({'error': 'missing_fields'}), 400

    if media_type not in ALLOWED_MEDIA:
        return jsonify({'error': 'invalid_media_type'}), 400

    photo_path = None
    if photo_file and photo_file.filename:
        ext       = os.path.splitext(photo_file.filename)[1].lower()
        filename  = f"col_{uid}_{int(datetime.now().timestamp())}{ext}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        photo_file.save(save_path)
        photo_path = f"uploads/{filename}"

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        INSERT INTO collection
            (user_id, "trackId", "trackName", "artistName", "artworkUrl100",
             media_type, photo, is_public, discogs_id, year, label, catno, country)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (uid, trackId, trackName, artistName, artworkUrl100, media_type,
          photo_path, is_public, discogs_id, year, label, catno, country))
    new_id = c.fetchone()['id']
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': new_id})


# ── Deletar item ──────────────────────────────────────────────────────────────

@bp.route('/collection/delete', methods=['POST'])
def delete_from_collection():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    data    = request.get_json(force=True)
    item_id = data.get('id')

    conn = get_db()
    c    = _cursor(conn)
    c.execute("DELETE FROM collection WHERE id=%s AND user_id=%s", (item_id, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Alternar visibilidade ─────────────────────────────────────────────────────

@bp.route('/collection/toggle_visibility', methods=['POST'])
def toggle_visibility():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    data    = request.get_json(force=True)
    item_id = data.get('id')

    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT is_public FROM collection WHERE id=%s AND user_id=%s", (item_id, uid))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not_found'}), 404

    new_val = 0 if row['is_public'] else 1
    c.execute("UPDATE collection SET is_public=%s WHERE id=%s AND user_id=%s", (new_val, item_id, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'is_public': new_val})