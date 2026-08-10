from flask import Blueprint, request, jsonify, session, current_app
from models import get_db
from datetime import datetime
import psycopg2.extras
import os
from extensions import limiter

bp = Blueprint('library', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def current_user_id():
    return session.get('user_id')

def _safe(s, default):
    if not s:
        return default
    s = str(s).strip()
    if s.lower() == 'undefined':
        return default
    return s

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def _ensure_list(conn, user_id, name):
    c = _cursor(conn)
    c.execute("SELECT id FROM lists WHERE user_id=%s AND name=%s", (user_id, name))
    row = c.fetchone()
    if row:
        return row["id"]
    c.execute(
        "INSERT INTO lists (user_id, name) VALUES (%s, %s) RETURNING id",
        (user_id, name)
    )
    conn.commit()
    return c.fetchone()["id"]


# ── Favoritos ─────────────────────────────────────────────────────────────────

@bp.route('/favorite', methods=['POST'])
@limiter.limit("30 per minute")
def toggle_favorite():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data    = request.get_json(force=True)
    trackId = _safe(data.get("trackId") or data.get("collectionId"), "")
    if not trackId:
        return jsonify({"error": "missing_track_id"}), 400

    title  = _safe(data.get("trackName") or data.get("collectionName"), "Sem título")
    artist = _safe(data.get("artistName"), "Desconhecido")
    cover  = _safe(data.get("artworkUrl100"), "/static/img/placeholder.png")

    conn = get_db()
    c    = _cursor(conn)

    c.execute('SELECT 1 FROM favorites WHERE user_id=%s AND "trackId"=%s', (uid, trackId))
    exists = c.fetchone()

    if exists:
        c.execute('DELETE FROM favorites WHERE user_id=%s AND "trackId"=%s', (uid, trackId))
        status = "unfavorited"
    else:
        c.execute("""
            INSERT INTO favorites (user_id, "trackId", "trackName", "artistName", "artworkUrl100")
            VALUES (%s, %s, %s, %s, %s)
        """, (uid, trackId, title, artist, cover))
        status = "favorited"

    conn.commit()
    conn.close()
    return jsonify({"success": True, "status": status})


# ── Avaliar ───────────────────────────────────────────────────────────────────

@bp.route('/rate', methods=['POST'])
@limiter.limit("30 per minute")
def rate():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data    = request.get_json(force=True)
    trackId = _safe(data.get("trackId") or data.get("collectionId"), "")
    rating  = int(data.get("rating", 0))
    title   = _safe(data.get("trackName") or data.get("collectionName"), "Sem título")
    artist  = _safe(data.get("artistName"), "Desconhecido")
    cover   = _safe(data.get("artworkUrl100"), "/static/img/placeholder.png")

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        INSERT INTO library (user_id, "trackId", "trackName", "artistName", "artworkUrl100", rating, "addedAt")
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(user_id, "trackId")
        DO UPDATE SET rating = EXCLUDED.rating
    """, (uid, trackId, title, artist, cover, rating, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ── Listas GET/CREATE ─────────────────────────────────────────────────────────

@bp.route('/lists', methods=['GET', 'POST'])
@limiter.limit("15 per minute")
def lists():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    conn = get_db()
    c    = _cursor(conn)
    _ensure_list(conn, uid, "Quero ouvir")

    if request.method == "GET":
        c.execute('SELECT * FROM lists WHERE user_id=%s ORDER BY "createdAt" DESC', (uid,))
        rows = [dict(r) for r in c.fetchall()]
        for r in rows:
            c.execute("""
                SELECT "artworkUrl100" FROM list_items
                WHERE list_id=%s ORDER BY "addedAt" DESC LIMIT 1
            """, (r["id"],))
            img = c.fetchone()
            r["auto_cover"] = img["artworkUrl100"] if img else None
        conn.close()
        return jsonify(rows)

    if request.content_type and 'multipart' in request.content_type:
        name        = _safe(request.form.get("name"), "")
        description = request.form.get("description", "").strip()
        is_public   = int(request.form.get("is_public", 1))
        cover_file  = request.files.get("cover")
    else:
        data        = request.get_json(force=True)
        name        = _safe(data.get("name"), "")
        description = (data.get("description") or "").strip()
        is_public   = int(data.get("is_public", 1))
        cover_file  = None

    if not name:
        return jsonify({"error": "missing_list_name"}), 400

    cover_path = None
    if cover_file and cover_file.filename:
        ext       = os.path.splitext(cover_file.filename)[1].lower()
        filename  = f"list_{uid}_{int(datetime.now().timestamp())}{ext}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        cover_file.save(save_path)
        cover_path = f"uploads/{filename}"

    try:
        c.execute("""
            INSERT INTO lists (user_id, name, description, is_public, cover)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (uid, name, description, is_public, cover_path))
        new_id = c.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"success": True, "list_id": new_id})
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({"error": "exists"}), 400


# ── Editar lista ──────────────────────────────────────────────────────────────

@bp.route('/lists/edit', methods=['POST'])
def edit_list():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    if request.content_type and 'multipart' in request.content_type:
        list_id     = request.form.get("id")
        name        = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        is_public   = int(request.form.get("is_public", 1))
        cover_file  = request.files.get("cover")
    else:
        data        = request.get_json(force=True)
        list_id     = data.get("id")
        name        = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        is_public   = int(data.get("is_public", 1))
        cover_file  = None

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT user_id FROM lists WHERE id=%s", (list_id,))
    row = c.fetchone()
    if not row or row["user_id"] != uid:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    cover_path = None
    if cover_file and cover_file.filename:
        ext       = os.path.splitext(cover_file.filename)[1].lower()
        filename  = f"list_{uid}_{int(datetime.now().timestamp())}{ext}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        cover_file.save(save_path)
        cover_path = f"uploads/{filename}"

    if cover_path:
        c.execute("""
            UPDATE lists SET name=%s, description=%s, is_public=%s, cover=%s
            WHERE id=%s AND user_id=%s
        """, (name, description, is_public, cover_path, list_id, uid))
    else:
        c.execute("""
            UPDATE lists SET name=%s, description=%s, is_public=%s
            WHERE id=%s AND user_id=%s
        """, (name, description, is_public, list_id, uid))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ── Adicionar item na lista ───────────────────────────────────────────────────

@bp.route('/lists/add', methods=['POST'])
def list_add_item():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data      = request.get_json(force=True)
    list_id   = data.get("list_id")
    list_name = _safe(data.get("listName"), "")
    trackId   = _safe(data.get("trackId") or data.get("collectionId"), "")
    title     = _safe(data.get("trackName") or data.get("collectionName"), "Sem título")
    artist    = _safe(data.get("artistName"), "Desconhecido")
    cover     = _safe(data.get("artworkUrl100"), "/static/img/placeholder.png")

    if not trackId:
        return jsonify({"error": "missing_track"}), 400

    conn = get_db()
    if not list_id:
        list_id = _ensure_list(conn, uid, list_name)

    c = _cursor(conn)
    try:
        c.execute("""
            INSERT INTO list_items (list_id, "trackId", "trackName", "artistName", "artworkUrl100")
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (list_id, trackId, title, artist, cover))
        conn.commit()
    except Exception:
        conn.rollback()

    conn.close()
    return jsonify({"success": True})


# ── Ouvidas ───────────────────────────────────────────────────────────────────

@bp.route('/listened', methods=['POST'])
def mark_listened():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data    = request.get_json(force=True)
    trackId = _safe(data.get("trackId"), "")
    title   = _safe(data.get("trackName"), "Sem título")
    artist  = _safe(data.get("artistName"), "Desconhecido")
    cover   = _safe(data.get("artworkUrl100"), "/static/img/placeholder.png")

    if not trackId:
        return jsonify({"error": "missing_track_id"}), 400

    now = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        INSERT INTO listened (user_id, "trackId", "trackName", "artistName", "artworkUrl100", "listenedAt")
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (uid, trackId, title, artist, cover, now))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ── Diário ────────────────────────────────────────────────────────────────────

@bp.route('/diary', methods=['POST'])
def diary_add():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data    = request.get_json(force=True)
    trackId = data.get("trackId")
    title   = data.get("trackName")
    artist  = data.get("artistName")
    cover   = data.get("artworkUrl100")
    date    = data.get("listenedAt")

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        INSERT INTO diary (user_id, "trackId", "trackName", "artistName", "artworkUrl100", "listenedAt")
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (uid, trackId, title, artist, cover, date))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@bp.route('/diary/delete', methods=['POST'])
def diary_delete():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data     = request.get_json()
    diary_id = data.get("id")

    conn = get_db()
    c    = _cursor(conn)
    c.execute("DELETE FROM diary WHERE id=%s AND user_id=%s", (diary_id, uid))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@bp.route('/diary/update', methods=['POST'])
def diary_update():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data     = request.get_json()
    diary_id = data.get("id")
    date     = data.get("listenedAt")

    conn = get_db()
    c    = _cursor(conn)
    c.execute('UPDATE diary SET "listenedAt"=%s WHERE id=%s AND user_id=%s', (date, diary_id, uid))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ── Média das notas ───────────────────────────────────────────────────────────

@bp.route('/average_rating/<trackId>')
def average_rating(trackId):
    conn = get_db()
    c    = _cursor(conn)
    c.execute(
        'SELECT AVG(rating) AS avg, COUNT(*) AS count FROM library WHERE "trackId"=%s AND rating>0',
        (trackId,)
    )
    row = c.fetchone()
    conn.close()

    avg = round(float(row["avg"]), 1) if row["avg"] else 0
    return jsonify({"average": avg, "count": row["count"]})


# ── Reviews ───────────────────────────────────────────────────────────────────

@bp.route('/review', methods=['POST'])
@limiter.limit("10 per minute")
def add_review():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data    = request.get_json(force=True)
    trackId = data.get("trackId")
    text    = (data.get("text") or "").strip()

    if not trackId or not text:
        return jsonify({"error": "missing_fields"}), 400

    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT username FROM users WHERE id=%s", (uid,))
    uname = c.fetchone()["username"]

    c.execute("""
        INSERT INTO reviews (user_id, "trackId", username, text, "createdAt")
        VALUES (%s, %s, %s, %s, %s)
    """, (uid, trackId, uname, text, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@bp.route('/reviews/<trackId>')
def list_reviews(trackId):
    uid = current_user_id()

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT
            r.id,
            r.user_id,
            r."trackId",
            COALESCE(r.username, u.username) AS username,
            r.text,
            r."createdAt",
            u.avatar
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r."trackId"=%s
        ORDER BY r.id DESC
        LIMIT 100
    """, (trackId,))

    rows = [dict(r) for r in c.fetchall()]

    for row in rows:
        row["avatar"] = row["avatar"] or "img/default.png"
        try:
            dt = datetime.fromisoformat(str(row["createdAt"]))
            row["createdAt"] = dt.strftime("%d/%m/%Y")
        except Exception:
            pass

        c.execute("SELECT COUNT(*) AS cnt FROM review_likes WHERE review_id=%s", (row["id"],))
        row["likes_count"] = c.fetchone()["cnt"]

        row["liked_by_me"] = False
        if uid:
            c.execute("SELECT 1 FROM review_likes WHERE user_id=%s AND review_id=%s", (uid, row["id"]))
            row["liked_by_me"] = c.fetchone() is not None

    conn.close()
    return jsonify(rows)


@bp.route('/review/edit', methods=['POST'])
def edit_review():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    data      = request.get_json(force=True)
    review_id = data.get('id')
    text      = (data.get('text') or '').strip()

    if not text:
        return jsonify({'error': 'empty_text'}), 400

    conn = get_db()
    c    = _cursor(conn)
    c.execute("UPDATE reviews SET text=%s WHERE id=%s AND user_id=%s", (text, review_id, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@bp.route('/review/delete', methods=['POST'])
def delete_review():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    data      = request.get_json(force=True)
    review_id = data.get('id')

    conn = get_db()
    c    = _cursor(conn)
    c.execute("DELETE FROM reviews WHERE id=%s AND user_id=%s", (review_id, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Listas — deletar, remover item ────────────────────────────────────────────

@bp.route('/lists/delete', methods=['POST'])
def delete_list():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data    = request.get_json()
    list_id = data.get("id")

    conn = get_db()
    c    = _cursor(conn)
    c.execute("DELETE FROM list_likes WHERE list_id=%s", (list_id,))
    c.execute("DELETE FROM list_saves WHERE list_id=%s", (list_id,))
    c.execute("DELETE FROM list_items WHERE list_id=%s", (list_id,))
    c.execute("DELETE FROM lists WHERE id=%s AND user_id=%s", (list_id, uid))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@bp.route('/lists/remove_item', methods=['POST'])
def remove_list_item():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data     = request.get_json()
    list_id  = data.get("list_id")
    track_id = data.get("trackId")

    conn = get_db()
    c    = _cursor(conn)
    c.execute('DELETE FROM list_items WHERE list_id=%s AND "trackId"=%s', (list_id, track_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ── Últimas avaliações ────────────────────────────────────────────────────────

@bp.route('/recent_ratings')
def recent_ratings():
    uid = current_user_id()
    if not uid:
        return jsonify([])

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT "trackId", "trackName", "artistName", "artworkUrl100", rating
        FROM library
        WHERE user_id=%s AND rating > 0
        ORDER BY "addedAt" DESC
        LIMIT 10
    """, (uid,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)