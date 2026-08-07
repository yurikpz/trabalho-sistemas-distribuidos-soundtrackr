from flask import Blueprint, request, jsonify, session
from models import get_db
from routes.notifications import create_notification
import psycopg2.extras

bp = Blueprint('interactions', __name__)


def current_user_id():
    return session.get('user_id')

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Like em review ────────────────────────────────────────────────────────────

@bp.route('/review/<int:review_id>/like', methods=['POST'])
def toggle_review_like(review_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT user_id FROM reviews WHERE id=%s", (review_id,))
    review = c.fetchone()
    if not review:
        conn.close()
        return jsonify({'error': 'not_found'}), 404

    c.execute("SELECT id FROM review_likes WHERE user_id=%s AND review_id=%s", (uid, review_id))
    existing = c.fetchone()

    if existing:
        c.execute("DELETE FROM review_likes WHERE user_id=%s AND review_id=%s", (uid, review_id))
        liked = False
    else:
        c.execute("INSERT INTO review_likes (user_id, review_id) VALUES (%s, %s)", (uid, review_id))
        liked = True

    conn.commit()

    c.execute("SELECT COUNT(*) AS cnt FROM review_likes WHERE review_id=%s", (review_id,))
    likes_count = c.fetchone()['cnt']
    conn.close()

    if liked:
        create_notification(review['user_id'], 'review_like', uid, review_id)

    return jsonify({'liked': liked, 'likes_count': likes_count})


# ── Like em lista ─────────────────────────────────────────────────────────────

@bp.route('/lists/<int:list_id>/like', methods=['POST'])
def toggle_list_like(list_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT user_id FROM lists WHERE id=%s", (list_id,))
    lst = c.fetchone()
    if not lst:
        conn.close()
        return jsonify({'error': 'not_found'}), 404

    c.execute("SELECT id FROM list_likes WHERE user_id=%s AND list_id=%s", (uid, list_id))
    existing = c.fetchone()

    if existing:
        c.execute("DELETE FROM list_likes WHERE user_id=%s AND list_id=%s", (uid, list_id))
        liked = False
    else:
        c.execute("INSERT INTO list_likes (user_id, list_id) VALUES (%s, %s)", (uid, list_id))
        liked = True

    conn.commit()

    c.execute("SELECT COUNT(*) AS cnt FROM list_likes WHERE list_id=%s", (list_id,))
    likes_count = c.fetchone()['cnt']
    conn.close()

    if liked:
        create_notification(lst['user_id'], 'list_like', uid, list_id)

    return jsonify({'liked': liked, 'likes_count': likes_count})


# ── Salvar lista (sem notificação) ────────────────────────────────────────────

@bp.route('/lists/<int:list_id>/save', methods=['POST'])
def toggle_list_save(list_id):
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT id FROM lists WHERE id=%s", (list_id,))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'not_found'}), 404

    c.execute("SELECT id FROM list_saves WHERE user_id=%s AND list_id=%s", (uid, list_id))
    existing = c.fetchone()

    if existing:
        c.execute("DELETE FROM list_saves WHERE user_id=%s AND list_id=%s", (uid, list_id))
        saved = False
    else:
        c.execute("INSERT INTO list_saves (user_id, list_id) VALUES (%s, %s)", (uid, list_id))
        saved = True

    conn.commit()

    c.execute("SELECT COUNT(*) AS cnt FROM list_saves WHERE list_id=%s", (list_id,))
    saves_count = c.fetchone()['cnt']
    conn.close()

    return jsonify({'saved': saved, 'saves_count': saves_count})


# ── Estatísticas de uma lista (likes, saves, se o usuário curtiu/salvou) ──────

@bp.route('/lists/<int:list_id>/stats')
def list_stats(list_id):
    uid = current_user_id()

    conn = get_db()
    c    = _cursor(conn)

    c.execute("SELECT COUNT(*) AS cnt FROM list_likes WHERE list_id=%s", (list_id,))
    likes_count = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) AS cnt FROM list_saves WHERE list_id=%s", (list_id,))
    saves_count = c.fetchone()['cnt']

    liked_by_me = False
    saved_by_me = False
    if uid:
        c.execute("SELECT 1 FROM list_likes WHERE user_id=%s AND list_id=%s", (uid, list_id))
        liked_by_me = c.fetchone() is not None

        c.execute("SELECT 1 FROM list_saves WHERE user_id=%s AND list_id=%s", (uid, list_id))
        saved_by_me = c.fetchone() is not None

    conn.close()

    return jsonify({
        'likes_count': likes_count,
        'saves_count': saves_count,
        'liked_by_me': liked_by_me,
        'saved_by_me': saved_by_me,
    })