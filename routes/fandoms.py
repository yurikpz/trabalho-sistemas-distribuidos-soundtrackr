from flask import Blueprint, request, jsonify, session
from models import get_db
from routes.notifications import create_notification
from extensions import limiter
import psycopg2.extras
import math

bp = Blueprint('fandoms', __name__)


def current_user_id():
    return session.get('user_id')

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Sistema de nível/XP ─────────────────────────────────────────────────────

def calc_level(xp):
    return 1 + int(math.sqrt(xp / 400))

def xp_for_level(level):
    return 400 * (level - 1) ** 2

def add_xp(user_id, fandom_id, amount):
    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        UPDATE user_fandoms SET xp = xp + %s
        WHERE user_id=%s AND fandom_id=%s
    """, (amount, user_id, fandom_id))
    conn.commit()
    conn.close()

def _mark_like_rewarded(user_id, post_id):
    conn = get_db()
    c    = _cursor(conn)
    try:
        c.execute("""
            INSERT INTO fandom_post_like_xp_log (user_id, post_id)
            VALUES (%s, %s)
        """, (user_id, post_id))
        conn.commit()
    except Exception:
        conn.rollback()
    conn.close()


# ── Buscar fandoms (autocomplete) ──────────────────────────────────────────────

@bp.route('/fandoms/search')
def search_fandoms():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT f.id, f.name, f.artist_name, f.color,
               (SELECT COUNT(*) FROM user_fandoms WHERE fandom_id=f.id) AS member_count
        FROM fandoms f
        WHERE f.name ILIKE %s OR f.artist_name ILIKE %s
        ORDER BY (f.artist_name IS NOT NULL) DESC, f.name
        LIMIT 20
    """, (f"%{q}%", f"%{q}%"))
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
        SELECT f.id, f.name, f.artist_name, f.color
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


# ── Recomendações de fandom (Fanchat) ──────────────────────────────────────────

@bp.route('/fandoms/recommended')
def recommended_fandoms():
    uid = current_user_id()
    if not uid:
        return jsonify([])

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
        LIMIT 10
    """, (uid, uid))
    my_artists = [r['artistName'] for r in c.fetchall()]

    c.execute("SELECT fandom_id FROM user_fandoms WHERE user_id=%s", (uid,))
    joined_ids = [r['fandom_id'] for r in c.fetchall()]

    recommended = []
    if my_artists:
        placeholders = " OR ".join(["f.artist_name ILIKE %s"] * len(my_artists))
        params = [f"%{a}%" for a in my_artists]

        query = f"""
            SELECT f.id, f.name, f.artist_name, f.color,
                   (SELECT COUNT(*) FROM user_fandoms WHERE fandom_id=f.id) AS member_count
            FROM fandoms f
            WHERE ({placeholders})
        """
        if joined_ids:
            query += " AND f.id != ALL(%s)"
            params.append(joined_ids)

        query += " LIMIT 12"

        c.execute(query, params)
        recommended = [dict(r) for r in c.fetchall()]

    conn.close()
    return jsonify({'items': recommended, 'based_on': my_artists[:3]})


# ── Todos os fandoms (navegação/descoberta) ────────────────────────────────────

@bp.route('/fandoms/browse')
def browse_fandoms():
    letter = request.args.get('letter', '').strip().upper()

    conn = get_db()
    c    = _cursor(conn)

    if letter and letter.isalpha():
        c.execute("""
            SELECT f.id, f.name, f.artist_name, f.color,
                   (SELECT COUNT(*) FROM user_fandoms WHERE fandom_id=f.id) AS member_count
            FROM fandoms f
            WHERE f.name ILIKE %s
            ORDER BY f.name
            LIMIT 60
        """, (f"{letter}%",))
    else:
        c.execute("""
            SELECT f.id, f.name, f.artist_name, f.color,
                   (SELECT COUNT(*) FROM user_fandoms WHERE fandom_id=f.id) AS member_count
            FROM fandoms f
            ORDER BY (SELECT COUNT(*) FROM user_fandoms WHERE fandom_id=f.id) DESC, f.name
            LIMIT 60
        """)

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)


# ── Página do fandom (fórum) — dados ────────────────────────────────────────────

@bp.route('/fandom/<int:fandom_id>/info')
def fandom_info(fandom_id):
    uid = current_user_id()

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT id, name, artist_name, color FROM fandoms WHERE id=%s", (fandom_id,))
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
        'artist_name': fandom['artist_name'],
        'color': fandom['color'] or '#7a8a9a',
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

    add_xp(uid, fandom_id, 6)

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
    c.execute("DELETE FROM fandom_post_like_xp_log WHERE post_id=%s", (post_id,))
    c.execute("DELETE FROM fandom_posts WHERE id=%s AND user_id=%s", (post_id, uid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Like em post (com proteção anti-farm) ──────────────────────────────────────

@bp.route('/fandom/post/<int:post_id>/like', methods=['POST'])
@limiter.limit("30 per minute")
def toggle_post_like(post_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT user_id, fandom_id FROM fandom_posts WHERE id=%s", (post_id,))
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

    already_rewarded = False
    if liked:
        c.execute("""
            SELECT 1 FROM fandom_post_like_xp_log
            WHERE user_id=%s AND post_id=%s
        """, (uid, post_id))
        already_rewarded = c.fetchone() is not None

    conn.close()

    if liked:
        create_notification(post['user_id'], 'fandom_post_like', uid, post_id)

        if not already_rewarded:
            add_xp(uid, post['fandom_id'], 1)
            if post['user_id'] != uid:
                add_xp(post['user_id'], post['fandom_id'], 2)
            _mark_like_rewarded(uid, post_id)

    return jsonify({'liked': liked, 'likes_count': likes_count})


# ── Comentários ────────────────────────────────────────────────────────────────

@bp.route('/fandom/post/<int:post_id>/comments')
def list_comments(post_id):
    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT c.id, c.text, c."createdAt", c.parent_comment_id,
               u.id AS user_id, u.username, u.avatar
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

    data      = request.get_json(force=True)
    text      = (data.get('text') or '').strip()
    parent_id = data.get('parent_comment_id')
    if not text:
        return jsonify({'error': 'empty_text'}), 400

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT user_id, fandom_id FROM fandom_posts WHERE id=%s", (post_id,))
    post = c.fetchone()

    parent_owner_id = None
    if parent_id:
        c.execute("SELECT user_id FROM fandom_post_comments WHERE id=%s", (parent_id,))
        parent = c.fetchone()
        if parent:
            parent_owner_id = parent['user_id']

    c.execute("""
        INSERT INTO fandom_post_comments (post_id, user_id, text, parent_comment_id)
        VALUES (%s, %s, %s, %s) RETURNING id
    """, (post_id, uid, text, parent_id))
    new_id = c.fetchone()['id']
    conn.commit()
    conn.close()

    if post:
        is_own_post = post['user_id'] == uid

        if not is_own_post:
            add_xp(uid, post['fandom_id'], 4)
            create_notification(post['user_id'], 'fandom_comment', uid, post_id)
            add_xp(post['user_id'], post['fandom_id'], 2)

        if is_own_post and parent_id and parent_owner_id and parent_owner_id != uid:
            add_xp(uid, post['fandom_id'], 3)

    return jsonify({'success': True, 'id': new_id})


# ── Carteirinha (badge) ─────────────────────────────────────────────────────

@bp.route('/fandom/<int:fandom_id>/my_badge')
def my_badge(fandom_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT xp, is_public FROM user_fandoms
        WHERE user_id=%s AND fandom_id=%s
    """, (uid, fandom_id))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({'is_member': False})

    xp    = row['xp'] or 0
    level = calc_level(xp)
    next_level_xp = xp_for_level(level + 1)
    curr_level_xp = xp_for_level(level)
    progress = (xp - curr_level_xp) / max(1, next_level_xp - curr_level_xp)

    return jsonify({
        'is_member': True,
        'xp': xp,
        'level': level,
        'next_level_xp': next_level_xp,
        'progress': round(progress, 3),
        'is_public': bool(row['is_public']),
    })


@bp.route('/fandom/<int:fandom_id>/badge/toggle_visibility', methods=['POST'])
def toggle_badge_visibility(fandom_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT is_public FROM user_fandoms WHERE user_id=%s AND fandom_id=%s", (uid, fandom_id))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not_found'}), 404

    new_val = 0 if row['is_public'] else 1
    c.execute("""
        UPDATE user_fandoms SET is_public=%s
        WHERE user_id=%s AND fandom_id=%s
    """, (new_val, uid, fandom_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'is_public': bool(new_val)})


@bp.route('/user/<int:user_id>/badges')
def user_badges(user_id):
    uid = current_user_id()
    is_own = uid == user_id

    conn = get_db()
    c    = _cursor(conn)

    if is_own:
        c.execute("""
            SELECT f.id AS fandom_id, f.name, f.artist_name, f.color,
                   uf.xp, uf.is_public
            FROM user_fandoms uf
            JOIN fandoms f ON f.id = uf.fandom_id
            WHERE uf.user_id=%s AND uf.xp > 0
            ORDER BY uf.xp DESC
        """, (user_id,))
    else:
        c.execute("""
            SELECT f.id AS fandom_id, f.name, f.artist_name, f.color,
                   uf.xp, uf.is_public
            FROM user_fandoms uf
            JOIN fandoms f ON f.id = uf.fandom_id
            WHERE uf.user_id=%s AND uf.xp > 0 AND uf.is_public=1
            ORDER BY uf.xp DESC
        """, (user_id,))

    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    for r in rows:
        r['level'] = calc_level(r['xp'])

    return jsonify(rows)


@bp.route('/fandom/<int:fandom_id>/badge_card/<int:user_id>')
def badge_card_data(fandom_id, user_id):
    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT id, name, artist_name, color FROM fandoms WHERE id=%s", (fandom_id,))
    fandom = c.fetchone()

    c.execute("""
        SELECT xp, is_public FROM user_fandoms
        WHERE user_id=%s AND fandom_id=%s
    """, (user_id, fandom_id))
    uf = c.fetchone()

    c.execute("SELECT username, avatar FROM users WHERE id=%s", (user_id,))
    user = c.fetchone()

    conn.close()

    if not fandom or not uf or not user:
        return jsonify({'error': 'not_found'}), 404

    xp    = uf['xp'] or 0
    level = calc_level(xp)

    return jsonify({
        'fandom_name': fandom['name'],
        'artist_name': fandom['artist_name'],
        'color': fandom['color'] or '#7a8a9a',
        'username': user['username'],
        'avatar': user['avatar'] or 'img/default.png',
        'xp': xp,
        'level': level,
    })