from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from models import get_db
import psycopg2.extras
import os

bp = Blueprint('profile', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def current_user_id():
    return session.get('user_id')

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def get_user_by_id(uid):
    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT id, username, fandom, avatar, bio FROM users WHERE id=%s", (uid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_current_user_full():
    if not current_user_id():
        return None
    return get_user_by_id(current_user_id())

def _build_stats(uid, c):

    c.execute("SELECT COUNT(*) AS cnt FROM library WHERE user_id=%s AND rating > 0", (uid,))
    rated_count = c.fetchone()['cnt']

    c.execute("SELECT ROUND(AVG(rating)::numeric, 1) AS avg FROM library WHERE user_id=%s AND rating > 0", (uid,))
    row = c.fetchone()
    avg_rating = float(row['avg']) if row['avg'] else 0

    c.execute("SELECT COUNT(*) AS cnt FROM favorites WHERE user_id=%s", (uid,))
    fav_count = c.fetchone()['cnt']

    c.execute('SELECT COUNT(DISTINCT "trackId") AS cnt FROM listened WHERE user_id=%s', (uid,))
    listened_count = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) AS cnt FROM reviews WHERE user_id=%s", (uid,))
    review_count = c.fetchone()['cnt']

    c.execute("""
        SELECT "artistName", COUNT(*) AS cnt
        FROM library
        WHERE user_id=%s AND "artistName" IS NOT NULL AND "artistName" != ''
        GROUP BY "artistName"
        ORDER BY cnt DESC
        LIMIT 5
    """, (uid,))
    top_artists = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT rating, COUNT(*) AS cnt
        FROM library
        WHERE user_id=%s AND rating > 0
        GROUP BY rating
        ORDER BY rating DESC
    """, (uid,))
    rating_dist = {r['rating']: r['cnt'] for r in c.fetchall()}
    rating_dist = {i: rating_dist.get(i, 0) for i in range(5, 0, -1)}

    c.execute("SELECT COUNT(*) AS cnt FROM follows WHERE following_id=%s", (uid,))
    followers_count = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) AS cnt FROM follows WHERE follower_id=%s", (uid,))
    following_count = c.fetchone()['cnt']

    return {
        'rated_count':     rated_count,
        'avg_rating':      avg_rating,
        'fav_count':       fav_count,
        'listened_count':  listened_count,
        'review_count':    review_count,
        'top_artists':     top_artists,
        'rating_dist':     rating_dist,
        'followers_count': followers_count,
        'following_count': following_count,
    }


# ── Perfil do usuário logado ──────────────────────────────────────────────────

@bp.route('/perfil')
def perfil():
    if not current_user_id():
        return redirect(url_for('auth.login'))

    uid  = current_user_id()
    user = get_current_user_full()
    if not user:
        return redirect(url_for('auth.login'))

    if not user.get('avatar'):
        user['avatar'] = 'img/default.png'

    conn = get_db()
    c    = _cursor(conn)

    c.execute("""
        SELECT "trackId", "trackName", "artistName", "artworkUrl100"
        FROM favorites WHERE user_id=%s ORDER BY id DESC
    """, (uid,))
    fav_rows = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT "trackId", "trackName", "artistName", "artworkUrl100", "listenedAt"
        FROM listened WHERE user_id=%s
        ORDER BY "listenedAt" DESC, id DESC
    """, (uid,))
    listened_rows = [dict(r) for r in c.fetchall()]

    # Suas listas
    c.execute("""
        SELECT * FROM lists
        WHERE user_id=%s ORDER BY "createdAt" DESC
    """, (uid,))
    lists_rows = [dict(r) for r in c.fetchall()]

    for l in lists_rows:
        if not l.get("cover"):
            c.execute("""
                SELECT "artworkUrl100" FROM list_items
                WHERE list_id=%s ORDER BY "addedAt" DESC LIMIT 1
            """, (l['id'],))
            img = c.fetchone()
            l['auto_cover'] = img['artworkUrl100'] if img else None

    # Listas salvas
    c.execute("""
        SELECT l.*, u.username, u.avatar
        FROM list_saves ls
        JOIN lists l ON l.id = ls.list_id
        JOIN users u ON u.id = l.user_id
        WHERE ls.user_id=%s
        ORDER BY ls."createdAt" DESC
    """, (uid,))
    saved_lists_rows = [dict(r) for r in c.fetchall()]

    for l in saved_lists_rows:
        if not l.get("cover"):
            c.execute("""
                SELECT "artworkUrl100" FROM list_items
                WHERE list_id=%s ORDER BY "addedAt" DESC LIMIT 1
            """, (l['id'],))
            img = c.fetchone()
            l['auto_cover'] = img['artworkUrl100'] if img else None

    # Fandoms do usuário
    c.execute("""
        SELECT f.id, f.name
        FROM user_fandoms uf
        JOIN fandoms f ON f.id = uf.fandom_id
        WHERE uf.user_id=%s
        ORDER BY f.name
    """, (uid,))
    user_fandoms = [dict(r) for r in c.fetchall()]

    stats = _build_stats(uid, c)
    conn.close()

    return render_template(
        'perfil.html',
        user=user,
        favorites=fav_rows,
        ouvidas=listened_rows,
        listas=lists_rows,
        listas_salvas=saved_lists_rows,
        user_fandoms=user_fandoms,
        stats=stats,
        public_view=False
    )


# ── Editar perfil ─────────────────────────────────────────────────────────────

@bp.route('/editar_perfil', methods=['GET', 'POST'])
def editar_perfil():
    if not current_user_id():
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        return render_template('editar_perfil.html', user=get_current_user_full())

    username    = request.form.get('username', '').strip()
    bio         = request.form.get('bio', '').strip()
    avatar_file = request.files.get('avatar')

    avatar_path_db = None
    if avatar_file and avatar_file.filename:
        filename  = f"user_{current_user_id()}_{avatar_file.filename}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        avatar_file.save(save_path)
        avatar_path_db = f"uploads/{filename}"

    conn = get_db()
    c    = _cursor(conn)

    if avatar_path_db:
        c.execute(
            "UPDATE users SET username=%s, avatar=%s, bio=%s WHERE id=%s",
            (username, avatar_path_db, bio, current_user_id())
        )
    else:
        c.execute(
            "UPDATE users SET username=%s, bio=%s WHERE id=%s",
            (username, bio, current_user_id())
        )

    conn.commit()
    conn.close()

    session['username'] = username
    return redirect(url_for('profile.perfil'))


# ── Diário ────────────────────────────────────────────────────────────────────

@bp.route('/diary')
def diary_page():
    if not current_user_id():
        return redirect(url_for('auth.login'))

    uid  = current_user_id()
    user = get_current_user_full()

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT
            d.id, d."trackId", d."trackName", d."artistName", d."artworkUrl100", d."listenedAt",
            COALESCE(d.rating, l.rating, 0) AS rating,
            d.is_relisten
        FROM diary d
        LEFT JOIN library l ON d.user_id = l.user_id AND d."trackId" = l."trackId"
        WHERE d.user_id=%s
        ORDER BY d."listenedAt" DESC, d.id DESC
    """, (uid,))
    diary_rows = [dict(r) for r in c.fetchall()]
    conn.close()

    if not user.get('avatar'):
        user['avatar'] = 'img/default.png'

    return render_template('diary.html', user=user, diary=diary_rows)