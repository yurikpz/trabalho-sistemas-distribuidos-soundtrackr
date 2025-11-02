from flask import Blueprint, render_template, abort
from models import get_db

bp = Blueprint('public_profile', __name__)

@bp.route("/u/<int:user_id>")
def public_profile(user_id):
    conn = get_db()
    c = conn.cursor()

    # --- pegar dados do user ---
    c.execute("SELECT id, username, avatar, bio, fandom FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        abort(404)

    user = dict(user)
    user["avatar"] = user["avatar"] or "img/default.png"

    # --- FAVORITOS ---
    c.execute("""
        SELECT trackId, trackName, artistName, artworkUrl100
        FROM favorites WHERE user_id=?
        ORDER BY id DESC
        LIMIT 60
    """, (user_id,))
    favs = [dict(r) for r in c.fetchall()]

    # --- LISTAS ---
    c.execute("""
        SELECT id, name, createdAt
        FROM lists WHERE user_id=?
        ORDER BY createdAt DESC
    """, (user_id,))
    lists = [dict(r) for r in c.fetchall()]

    # pegar covers das listas
    for l in lists:
        c.execute("""
            SELECT artworkUrl100 FROM list_items
            WHERE list_id=? ORDER BY addedAt DESC LIMIT 1
        """, (l["id"],))
        img = c.fetchone()
        l["cover"] = img["artworkUrl100"] if img else None

    # --- OUVIRAM (listened) ---
    c.execute("""
        SELECT trackId, trackName, artistName, artworkUrl100, listenedAt
        FROM listened WHERE user_id=?
        ORDER BY listenedAt DESC LIMIT 60
    """, (user_id,))
    listened = [dict(r) for r in c.fetchall()]

    # --- REVIEWS ---
    c.execute("""
        SELECT r.trackId, r.text, r.createdAt, l.trackName, l.artistName, l.artworkUrl100
        FROM reviews r
        LEFT JOIN library l ON l.trackId = r.trackId AND l.user_id = r.user_id
        WHERE r.user_id=?
        ORDER BY r.id DESC
        LIMIT 60
    """, (user_id,))
    reviews = [dict(r) for r in c.fetchall()]

    # --- DIÁRIO ---
    c.execute("""
        SELECT trackId, trackName, artistName, artworkUrl100, listenedAt
        FROM diary
        WHERE user_id=?
        ORDER BY listenedAt DESC LIMIT 200
    """, (user_id,))
    diary = [dict(r) for r in c.fetchall()]

    conn.close()

    return render_template(
        "public_profile.html",
        user=user,
        favs=favs,
        lists=lists,
        listened=listened,
        reviews=reviews,
        diary=diary
    )
