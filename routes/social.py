from flask import Blueprint, request, jsonify, session
from models import get_db
from routes.notifications import create_notification
import psycopg2.extras
from extensions import limiter

bp = Blueprint('social', __name__)


def current_user_id():
    return session.get('user_id')

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Busca de usuários ─────────────────────────────────────────────────────────

@bp.route('/users/search')
@limiter.limit("30 per minute")
def search_users():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])

    uid = current_user_id()

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT id, username, avatar, bio, fandom
        FROM users
        WHERE username ILIKE %s AND id != %s
        ORDER BY username
        LIMIT 20
    """, (f"%{q}%", uid or -1))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    for r in rows:
        r['avatar'] = r['avatar'] or 'img/default.png'

    return jsonify(rows)


# ── Follow / Unfollow ─────────────────────────────────────────────────────────

@bp.route('/follow/<int:target_id>', methods=['POST'])
@limiter.limit("30 per minute")
def toggle_follow(target_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401
    if uid == target_id:
        return jsonify({'error': 'cannot_follow_yourself'}), 400

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT id FROM users WHERE id=%s", (target_id,))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'user_not_found'}), 404

    c.execute("SELECT id FROM follows WHERE follower_id=%s AND following_id=%s", (uid, target_id))
    existing = c.fetchone()

    if existing:
        c.execute("DELETE FROM follows WHERE follower_id=%s AND following_id=%s", (uid, target_id))
        following = False
    else:
        c.execute("INSERT INTO follows (follower_id, following_id) VALUES (%s, %s)", (uid, target_id))
        following = True

    conn.commit()

    c.execute("SELECT COUNT(*) AS cnt FROM follows WHERE following_id=%s", (target_id,))
    followers_count = c.fetchone()['cnt']

    conn.close()

    if following:
        create_notification(target_id, 'follow', uid)

    return jsonify({'following': following, 'followers_count': followers_count})


# ── Contadores ────────────────────────────────────────────────────────────────

@bp.route('/follow/stats/<int:user_id>')
def follow_stats(user_id):
    uid = current_user_id()

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT COUNT(*) AS cnt FROM follows WHERE following_id=%s", (user_id,))
    followers = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) AS cnt FROM follows WHERE follower_id=%s", (user_id,))
    following = c.fetchone()['cnt']

    i_follow = False
    if uid:
        c.execute("SELECT 1 FROM follows WHERE follower_id=%s AND following_id=%s", (uid, user_id))
        i_follow = c.fetchone() is not None

    conn.close()
    return jsonify({'followers': followers, 'following': following, 'i_follow': i_follow})


# ── Listas de seguidores/seguindo ─────────────────────────────────────────────

@bp.route('/follow/followers/<int:user_id>')
def list_followers(user_id):
    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT u.id, u.username, u.avatar, u.bio
        FROM follows f JOIN users u ON u.id = f.follower_id
        WHERE f.following_id = %s
        ORDER BY f."createdAt" DESC
    """, (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        r['avatar'] = r['avatar'] or 'img/default.png'
    return jsonify(rows)


@bp.route('/follow/following/<int:user_id>')
def list_following(user_id):
    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT u.id, u.username, u.avatar, u.bio
        FROM follows f JOIN users u ON u.id = f.following_id
        WHERE f.follower_id = %s
        ORDER BY f."createdAt" DESC
    """, (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        r['avatar'] = r['avatar'] or 'img/default.png'
    return jsonify(rows)


# ── Favoritos paginados ───────────────────────────────────────────────────────

@bp.route('/u/<int:user_id>/favorites')
def user_favorites(user_id):
    page     = int(request.args.get('page', 0))
    per_page = 20
    offset   = page * per_page

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT "trackId", "trackName", "artistName", "artworkUrl100"
        FROM favorites WHERE user_id=%s
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    """, (user_id, per_page, offset))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)


# ── Ouvidas paginadas ─────────────────────────────────────────────────────────

@bp.route('/u/<int:user_id>/listened')
def user_listened(user_id):
    page     = int(request.args.get('page', 0))
    per_page = 20
    offset   = page * per_page

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT "trackId", "trackName", "artistName", "artworkUrl100", "listenedAt"
        FROM listened WHERE user_id=%s
        ORDER BY "listenedAt" DESC, id DESC
        LIMIT %s OFFSET %s
    """, (user_id, per_page, offset))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)