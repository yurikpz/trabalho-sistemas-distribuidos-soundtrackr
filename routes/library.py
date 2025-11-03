from flask import Blueprint, request, jsonify, session
from models import get_db
from datetime import datetime

bp = Blueprint('library', __name__)


#HELPERS

def current_user_id():
    return session.get('user_id')

def _safe(s, default):
    if not s:
        return default
    s = str(s).strip()
    if s.lower() == 'undefined':
        return default
    return s

def _ensure_list(conn, user_id, name):
    c = conn.cursor()
    c.execute("SELECT id FROM lists WHERE user_id=? AND name=?", (user_id, name))
    row = c.fetchone()
    if row:
        return row["id"]
    c.execute("INSERT INTO lists (user_id, name) VALUES (?,?)", (user_id, name))
    conn.commit()
    return c.lastrowid


#FAVORITOS

@bp.route('/favorite', methods=['POST'])
def toggle_favorite():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(force=True)
    trackId = _safe(data.get("trackId") or data.get("collectionId"), "")
    if not trackId:
        return jsonify({"error": "missing_track_id"}), 400

    title = _safe(data.get("trackName") or data.get("collectionName"), "Sem título")
    artist = _safe(data.get("artistName"), "Desconhecido")
    cover = _safe(data.get("artworkUrl100"), "/static/img/placeholder.png")

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT 1 FROM favorites WHERE user_id=? AND trackId=?", (uid, trackId))
    exists = c.fetchone()

    if exists:
        c.execute("DELETE FROM favorites WHERE user_id=? AND trackId=?", (uid, trackId))
        status = "unfavorited"
    else:
        c.execute("""
            INSERT INTO favorites (user_id, trackId, trackName, artistName, artworkUrl100)
            VALUES (?,?,?,?,?)
        """, (uid, trackId, title, artist, cover))
        status = "favorited"

    conn.commit()
    conn.close()

    return jsonify({"success": True, "status": status})


#AVALIE A MÚSICA

@bp.route('/rate', methods=['POST'])
def rate():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(force=True)
    trackId = _safe(data.get("trackId") or data.get("collectionId"), "")
    rating = int(data.get("rating", 0))
    title = _safe(data.get("trackName") or data.get("collectionName"), "Sem título")
    artist = _safe(data.get("artistName"), "Desconhecido")
    cover = _safe(data.get("artworkUrl100"), "/static/img/placeholder.png")

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO library (user_id, trackId, trackName, artistName, artworkUrl100, rating, addedAt)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(user_id, trackId)
        DO UPDATE SET rating=excluded.rating
    """, (uid, trackId, title, artist, cover, rating, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


#LISTAS GET/CREATE

@bp.route('/lists', methods=['GET', 'POST'])
def lists():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    conn = get_db()
    c = conn.cursor()

    _ensure_list(conn, uid, "Quero ouvir")

    if request.method == "GET":
        c.execute("SELECT * FROM lists WHERE user_id=? ORDER BY createdAt DESC", (uid,))
        rows = [dict(r) for r in c.fetchall()]

        for r in rows:
            c.execute("""
                SELECT artworkUrl100 FROM list_items
                WHERE list_id=? ORDER BY addedAt DESC LIMIT 1
            """, (r["id"],))
            img = c.fetchone()
            r["cover"] = img["artworkUrl100"] if img else None

        conn.close()
        return jsonify(rows)

    data = request.get_json(force=True)
    name = _safe(data.get("name"), "")
    if not name:
        return jsonify({"error": "missing_list_name"}), 400

    try:
        c.execute("INSERT INTO lists (user_id, name) VALUES (?,?)", (uid, name))
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return jsonify({"success": True, "list_id": new_id})
    except:
        conn.close()
        return jsonify({"error": "exists"}), 400

#ADICIONAR ITEM NA LISTA

@bp.route('/lists/add', methods=['POST'])
def list_add_item():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(force=True)
    list_id = data.get("list_id")
    list_name = _safe(data.get("listName"), "")
    trackId = _safe(data.get("trackId") or data.get("collectionId"), "")
    title = _safe(data.get("trackName") or data.get("collectionName"), "Sem título")
    artist = _safe(data.get("artistName"), "Desconhecido")
    cover = _safe(data.get("artworkUrl100"), "/static/img/placeholder.png")

    if not trackId:
        return jsonify({"error": "missing_track"}), 400

    conn = get_db()

    if not list_id:
        list_id = _ensure_list(conn, uid, list_name)

    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO list_items (list_id, trackId, trackName, artistName, artworkUrl100)
            VALUES (?,?,?,?,?)
        """, (list_id, trackId, title, artist, cover))
        conn.commit()
    except:
        pass

    conn.close()
    return jsonify({"success": True})

#NÃO ESCREVE NO DIARIO

@bp.route('/listened', methods=['POST'])
def mark_listened():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(force=True)
    trackId = _safe(data.get("trackId"), "")
    title = _safe(data.get("trackName"), "Sem título")
    artist = _safe(data.get("artistName"), "Desconhecido")
    cover = _safe(data.get("artworkUrl100"), "/static/img/placeholder.png")

    if not trackId:
        return jsonify({"error": "missing_track_id"}), 400

    now = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        INSERT OR IGNORE INTO listened (user_id, trackId, trackName, artistName, artworkUrl100, listenedAt)
        VALUES (?,?,?,?,?,?)
    """, (uid, trackId, title, artist, cover, now))

    conn.commit()
    conn.close()
    return jsonify({"success": True})

# DIARIO

@bp.route('/diary', methods=['POST'])
def diary_add():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(force=True)
    trackId = data.get("trackId")
    title = data.get("trackName")
    artist = data.get("artistName")
    cover = data.get("artworkUrl100")
    date = data.get("listenedAt")

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO diary (user_id, trackId, trackName, artistName, artworkUrl100, listenedAt)
        VALUES (?,?,?,?,?,?)
    """, (uid, trackId, title, artist, cover, date))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@bp.route('/diary/delete', methods=['POST'])
def diary_delete():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json()
    diary_id = data.get("id")

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM diary WHERE id=? AND user_id=?", (diary_id, uid))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@bp.route('/diary/update', methods=['POST'])
def diary_update():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json()
    diary_id = data.get("id")
    date = data.get("listenedAt")

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE diary SET listenedAt=? WHERE id=? AND user_id=?", (date, diary_id, uid))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

#MEDIA DAS NOTAS

@bp.route('/average_rating/<trackId>')
def average_rating(trackId):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT AVG(rating) AS avg, COUNT(*) AS count FROM library WHERE trackId=? AND rating>0", (trackId,))
    row = c.fetchone()
    conn.close()

    avg = round(row["avg"], 1) if row["avg"] else 0
    return jsonify({"average": avg, "count": row["count"]})


#REVIEWS

@bp.route('/review', methods=['POST'])
def add_review():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(force=True)
    trackId = data.get("trackId")
    text = (data.get("text") or "").strip()

    if not trackId or not text:
        return jsonify({"error": "missing_fields"}), 400

    conn = get_db()
    c = conn.cursor()

    cu = conn.execute("SELECT username, avatar FROM users WHERE id=?", (uid,)).fetchone()
    uname = cu["username"]
    avatar = cu["avatar"]

    c.execute("""
        INSERT INTO reviews (user_id, trackId, username, text, createdAt)
        VALUES (?,?,?,?,?)
    """, (uid, trackId, uname, text, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return jsonify({"success": True})

@bp.route('/reviews/<trackId>')
def list_reviews(trackId):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT 
            r.id,
            r.user_id,
            r.trackId,
            COALESCE(r.username, u.username) AS username,
            r.text,
            r.createdAt,
            u.avatar
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.trackId=?
        ORDER BY r.id DESC
        LIMIT 100
    """, (trackId,))
    
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    for row in rows:
        row["avatar"] = row["avatar"] or "img/default.png"

        #  Formatar a data para DD/MM/YYYY
        try:
            dt = datetime.fromisoformat(row["createdAt"])
            row["createdAt"] = dt.strftime("%d/%m/%Y")
        except:
            pass

    return jsonify(rows)

# RENOMEAR, EXCLUIR ITEM E DELETAR LISTA


@bp.route('/lists/rename', methods=['POST'])
def rename_list():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401
    
    data = request.get_json()
    list_id = data.get("id")
    new_name = data.get("name")

    if not new_name:
        return jsonify({"error": "missing_name"}), 400

    conn = get_db()
    conn.execute("UPDATE lists SET name=? WHERE id=? AND user_id=?", (new_name, list_id, uid))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@bp.route('/lists/delete', methods=['POST'])
def delete_list():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json()
    list_id = data.get("id")

    conn = get_db()
    conn.execute("DELETE FROM list_items WHERE list_id=?", (list_id,))
    conn.execute("DELETE FROM lists WHERE id=? AND user_id=?", (list_id, uid))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


@bp.route('/lists/remove_item', methods=['POST'])
def remove_list_item():
    uid = current_user_id()
    if not uid:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json()
    list_id = data.get("list_id")
    track_id = data.get("trackId")

    conn = get_db()
    conn.execute("DELETE FROM list_items WHERE list_id=? AND trackId=?", (list_id, track_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

# ULTIMAS AVALIAÇÕES DO USUÁRIO

@bp.route('/recent_ratings')
def recent_ratings():
    uid = current_user_id()
    if not uid:
        return jsonify([])

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT trackId, trackName, artistName, artworkUrl100, rating
        FROM library
        WHERE user_id=? AND rating > 0
        ORDER BY addedAt DESC
        LIMIT 10
    """, (uid,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    return jsonify(rows)
