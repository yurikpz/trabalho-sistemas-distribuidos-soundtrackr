from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from models import get_db
import os

bp = Blueprint('profile', __name__)


#Helpers

def current_user_id():
    return session.get('user_id')

def get_user_by_id(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, fandom, avatar, bio FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_current_user_full():
    if not current_user_id():
        return None
    return get_user_by_id(current_user_id())


#PERFIL DO USUÁRIO LOGADO

@bp.route('/perfil')
def perfil():
    if not current_user_id():
        return redirect(url_for('auth.login'))

    user = get_current_user_full()
    if not user: return redirect(url_for('auth.login'))

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT trackId, trackName, artistName, artworkUrl100
        FROM favorites
        WHERE user_id=? ORDER BY id DESC
    """, (current_user_id(),))
    fav_rows = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT trackId, trackName, artistName, artworkUrl100, listenedAt
        FROM listened
        WHERE user_id=? 
        ORDER BY listenedAt DESC, id DESC
    """, (current_user_id(),))
    listened_rows = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT id, name, createdAt
        FROM lists
        WHERE user_id=? ORDER BY createdAt DESC
    """, (current_user_id(),))
    lists_rows = [dict(r) for r in c.fetchall()]

    conn.close()

    if not user.get('avatar'):
        user['avatar'] = 'img/default.png'

    return render_template(
        'perfil.html',
        user=user,
        favorites=fav_rows,
        ouvidas=listened_rows,
        listas=lists_rows,
        public_view=False
    )


#PERFIL PÚBLICO

@bp.route('/u/<int:user_id>')
def perfil_publico(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return redirect(url_for('profile.perfil'))

    if not user.get('avatar'):
        user['avatar'] = 'img/default.png'

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT trackId, trackName, artistName, artworkUrl100
        FROM favorites
        WHERE user_id=? ORDER BY id DESC
    """, (user_id,))
    fav_rows = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT trackId, trackName, artistName, artworkUrl100, listenedAt
        FROM listened
        WHERE user_id=? ORDER BY listenedAt DESC, id DESC
    """, (user_id,))
    listened_rows = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT id, name, createdAt 
        FROM lists WHERE user_id=? ORDER BY createdAt DESC
    """, (user_id,))
    lists_rows = [dict(r) for r in c.fetchall()]
    conn.close()

    return render_template(
        'perfil.html',
        user=user,
        favorites=fav_rows,
        ouvidas=listened_rows,
        listas=lists_rows,
        public_view=True
    )


#EDITAR PERFIL

@bp.route('/editar_perfil', methods=['GET','POST'])
def editar_perfil():
    if not current_user_id():
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        return render_template('editar_perfil.html', user=get_current_user_full())

    username = request.form.get('username','').strip()
    fandom = request.form.get('fandom','').strip()
    bio = request.form.get('bio','').strip()
    avatar_file = request.files.get('avatar')

    avatar_path_db = None
    if avatar_file and avatar_file.filename:
        filename = f"user_{current_user_id()}_{avatar_file.filename}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        avatar_file.save(save_path)
        avatar_path_db = f"uploads/{filename}"

    conn = get_db()
    c = conn.cursor()

    if avatar_path_db:
        c.execute("""
            UPDATE users SET username=?, fandom=?, avatar=?, bio=? WHERE id=?
        """, (username, fandom, avatar_path_db, bio, current_user_id()))
    else:
        c.execute("""
            UPDATE users SET username=?, fandom=?, bio=? WHERE id=?
        """, (username, fandom, bio, current_user_id()))

    conn.commit()
    conn.close()

    session['username'] = username
    return redirect(url_for('profile.perfil'))

#DIÁRIO
@bp.route('/diary')
def diary_page():
    if not current_user_id():
        return redirect(url_for('auth.login'))

    user = get_current_user_full()

    conn = get_db(); c = conn.cursor()
    c.execute("""
        SELECT 
            d.id, d.trackId, d.trackName, d.artistName, d.artworkUrl100, d.listenedAt,
            COALESCE(l.rating,0) AS rating
        FROM diary d
        LEFT JOIN library l
        ON d.user_id=l.user_id AND d.trackId=l.trackId
        WHERE d.user_id=?
        ORDER BY d.listenedAt DESC, d.id DESC
    """, (current_user_id(),))
    diary_rows = [dict(r) for r in c.fetchall()]
    conn.close()

    if not user.get('avatar'):
        user['avatar']='img/default.png'

    return render_template('diary.html', user=user, diary=diary_rows)
