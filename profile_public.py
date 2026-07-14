from flask import Blueprint, render_template, abort, session
from models import get_db
import psycopg2.extras

bp = Blueprint('public_profile', __name__)


def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


@bp.route("/u/<int:user_id>")
def public_profile(user_id):
    uid = session.get('user_id')
    uid     = int(uid) if uid else None
    user_id = int(user_id)

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT id, username, avatar, bio, fandom FROM users WHERE id=%s", (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        abort(404)

    user = dict(user)
    user["avatar"] = user["avatar"] or "img/default.png"

    c.execute("""
        SELECT "trackId", "trackName", "artistName", "artworkUrl100"
        FROM favorites WHERE user_id=%s ORDER BY id DESC LIMIT 60
    """, (user_id,))
    favs = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT id, name, "createdAt" FROM lists
        WHERE user_id=%s ORDER BY "createdAt" DESC
    """, (user_id,))
    lists = [dict(r) for r in c.fetchall()]

    for l in lists:
        c.execute("""
            SELECT "artworkUrl100" FROM list_items
            WHERE list_id=%s ORDER BY "addedAt" DESC LIMIT 1
        """, (l["id"],))
        img = c.fetchone()
        l["cover"] = img["artworkUrl100"] if img else None

    c.execute("""
        SELECT "trackId", "trackName", "artistName", "artworkUrl100", "listenedAt"
        FROM listened WHERE user_id=%s ORDER BY "listenedAt" DESC LIMIT 60
    """, (user_id,))
    listened = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT r."trackId", r.text, r."createdAt", l."trackName", l."artistName", l."artworkUrl100"
        FROM reviews r
        LEFT JOIN library l ON l."trackId" = r."trackId" AND l.user_id = r.user_id
        WHERE r.user_id=%s ORDER BY r.id DESC LIMIT 60
    """, (user_id,))
    reviews = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT "trackId", "trackName", "artistName", "artworkUrl100", "listenedAt"
        FROM diary WHERE user_id=%s ORDER BY "listenedAt" DESC LIMIT 200
    """, (user_id,))
    diary = [dict(r) for r in c.fetchall()]

    c.execute("SELECT COUNT(*) AS cnt FROM follows WHERE following_id=%s", (user_id,))
    followers_count = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) AS cnt FROM follows WHERE follower_id=%s", (user_id,))
    following_count = c.fetchone()['cnt']

    is_own_profile = (uid == user_id)

    i_follow = False
    if uid and not is_own_profile:
        c.execute("SELECT 1 FROM follows WHERE follower_id=%s AND following_id=%s", (uid, user_id))
        i_follow = c.fetchone() is not None

    conn.close()

    return render_template(
        "public_profile.html",
        user=user,
        favs=favs,
        lists=lists,
        listened=listened,
        reviews=reviews,
        diary=diary,
        followers_count=followers_count,
        following_count=following_count,
        i_follow=i_follow,
        is_own_profile=is_own_profile,
        logged_user_id=uid,
    )