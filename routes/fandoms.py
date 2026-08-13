from flask import Blueprint, request, jsonify, session
from models import get_db
from routes.notifications import create_notification
from extensions import limiter
import psycopg2.extras

bp = Blueprint('fandoms', __name__)


def current_user_id():
    return session.get('user_id')

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Buscar fandoms (autocomplete) ──────────────────────────────────────────────

@bp.route('/fandoms/search')
def search_fandoms():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT id, name FROM fandoms
        WHERE name ILIKE %s
        ORDER BY name
        LIMIT 15
    """, (f"%{q}%",))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)


# ── Fandoms do usuário logado ──────────────────────────────────────────────────

@bp.route('/fandoms/mine')
def my_fandoms():
    uid = current_user_id()
    if not uid:
        return jsonify([])

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT f.id, f.name
        FROM user_fandoms uf
        JOIN fandoms f ON f.id = uf.fandom_id
        WHERE uf.user_id=%s
        ORDER BY f.name
    """, (uid,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)


# ── Adicionar fandom ao perfil (cria se não existir) ───────────────────────────

@bp.route('/fandoms/add', methods=['POST'])
@limiter.limit("20 per minute")
def add_fandom():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()

    if not name or len(name) > 60:
        return jsonify({'error': 'invalid_name'}), 400

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT id FROM fandoms WHERE name ILIKE %s", (name,))
    row = c.fetchone()

    if row:
        fandom_id = row['id']
    else:
        c.execute("INSERT INTO fandoms (name) VALUES (%s) RETURNING id", (name,))
        fandom_id = c.fetchone()['id']
        conn.commit()

    try:
        c.execute("INSERT INTO user_fandoms (user_id, fandom_id) VALUES (%s, %s)", (uid, fandom_id))
        conn.commit()
    except Exception:
        conn.rollback()

    conn.close()
    return jsonify({'success': True, 'id': fandom_id, 'name': name})


# ── Remover fandom do perfil ────────────────────────────────────────────────────

@bp.route('/fandoms/remove', methods=['POST'])
def remove_fandom():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    data      = request.get_json(force=True)
    fandom_id = data.get('fandom_id')

    conn = get_db()
    c    = _cursor(conn)
    c.execute("DELETE FROM user_fandoms WHERE user_id=%s AND fandom_id=%s", (uid, fandom_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Página do fandom (fórum) — dados ────────────────────────────────────────────

@bp.route('/fandom/<int:fandom_id>/info')
def fandom_info(fandom_id):
    uid = current_user_id()

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT id, name FROM fandoms WHERE id=%s", (fandom_id,))
    fandom = c.fetchone()
    if not fandom:
        conn.close()
        return jsonify({'error': 'not_found'}), 404

    c.execute("SELECT COUNT(*) AS cnt FROM user_fandoms WHERE fandom_id=%s", (fandom_id,))
    member_count = c.fetchone()['cnt']

    is_member = False
    if uid:
        c.execute("SELECT 1 FROM user_fandoms WHERE user_id=%s AND fandom_id=%s", (uid, fandom_id))
        is_member = c.fetchone() is not None

    conn.close()
    return jsonify({
        'id': fandom['id'],
        'name': fandom['name'],
        'member_count': member_count,
        'is_member': is_member,
    })


# ── Posts do fandom (paginado) ──────────────────────────────────────────────────

@bp.route('/fandom/<int:fandom_id>/posts')
def fandom_posts(fandom_id):
    uid      = current_user_id()
    page     = int(request.args.get('page', 0))
    per_page = 15
    offset   = page * per_page

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT
            p.id, p.title, p.text, p."createdAt",
            u.id AS user_id, u.username, u.avatar
        FROM fandom_posts p
        JOIN users u ON u.id = p.user_id
        WHERE p.fandom_id=%s
        ORDER BY p."createdAt" DESC
        LIMIT %s OFFSET %s
    """, (fandom_id, per_page, offset))
    posts = [dict(r) for r in c.fetchall()]

    for post in posts:
        post['avatar'] = post['avatar'] or 'img/default.png'

        c.execute("SELECT COUNT(*) AS cnt FROM fandom_post_likes WHERE post_id=%s", (post['id'],))
        post['likes_count'] = c.fetchone()['cnt']

        c.execute("SELECT COUNT(*) AS cnt FROM fandom_post_comments WHERE post_id=%s", (post['id'],))
        post['comments_count'] = c.fetchone()['cnt']

        post['liked_by_me'] = False
        if uid:
            c.execute("SELECT 1 FROM fandom_post_likes WHERE user_id=%s AND post_id=%s", (uid, post['id']))
            post['liked_by_me'] = c.fetchone() is not None

    conn.close()
    return jsonify(posts)


# ── Criar post ───────────────────────────────────────────────────────────────

@bp.route('/fandom/<int:fandom_id>/posts/create', methods=['POST'])
@limiter.limit("10 per minute")
def create_post(fandom_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    data  = request.get_json(force=True)
    title = (data.get('title') or '').strip()
    text  = (data.get('text') or '').strip()

    if not title:
        return jsonify({'error': 'missing_title'}), 400

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        INSERT INTO fandom_posts (fandom_id, user_id, title, text)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (fandom_id, uid, title, text))
    new_id = c.fetchone()['id']
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': new_id})


@bp.route('/fandom/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)
    c.execute("DELETE FROM fandom_post_comments WHERE post_id=%s", (post_id,))
    c.execute("DELETE FROM fandom_post_likes WHERE post_id=%s", (post_id,))
    c.execute("DELETE FROM fandom_posts WHERE id=%s AND user_id=%s", (post_id, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Like em post ─────────────────────────────────────────────────────────────

@bp.route('/fandom/post/<int:post_id>/like', methods=['POST'])
@limiter.limit("30 per minute")
def toggle_post_like(post_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT user_id FROM fandom_posts WHERE id=%s", (post_id,))
    post = c.fetchone()
    if not post:
        conn.close()
        return jsonify({'error': 'not_found'}), 404

    c.execute("SELECT id FROM fandom_post_likes WHERE user_id=%s AND post_id=%s", (uid, post_id))
    existing = c.fetchone()

    if existing:
        c.execute("DELETE FROM fandom_post_likes WHERE user_id=%s AND post_id=%s", (uid, post_id))
        liked = False
    else:
        c.execute("INSERT INTO fandom_post_likes (user_id, post_id) VALUES (%s, %s)", (uid, post_id))
        liked = True

    conn.commit()

    c.execute("SELECT COUNT(*) AS cnt FROM fandom_post_likes WHERE post_id=%s", (post_id,))
    likes_count = c.fetchone()['cnt']
    conn.close()

    if liked:
        create_notification(post['user_id'], 'fandom_post_like', uid, post_id)

    return jsonify({'liked': liked, 'likes_count': likes_count})


# ── Comentários ────────────────────────────────────────────────────────────────

@bp.route('/fandom/post/<int:post_id>/comments')
def list_comments(post_id):
    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT c.id, c.text, c."createdAt", u.id AS user_id, u.username, u.avatar
        FROM fandom_post_comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.post_id=%s
        ORDER BY c."createdAt" ASC
    """, (post_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        r['avatar'] = r['avatar'] or 'img/default.png'
    return jsonify(rows)


@bp.route('/fandom/post/<int:post_id>/comment', methods=['POST'])
@limiter.limit("20 per minute")
def add_comment(post_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    data = request.get_json(force=True)
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'empty_text'}), 400

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT user_id FROM fandom_posts WHERE id=%s", (post_id,))
    post = c.fetchone()

    c.execute("""
        INSERT INTO fandom_post_comments (post_id, user_id, text)
        VALUES (%s, %s, %s) RETURNING id
    """, (post_id, uid, text))
    new_id = c.fetchone()['id']
    conn.commit()
    conn.close()

    if post and post['user_id'] != uid:
        create_notification(post['user_id'], 'fandom_comment', uid, post_id)

    return jsonify({'success': True, 'id': new_id})