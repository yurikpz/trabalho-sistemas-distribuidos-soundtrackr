from flask import Blueprint, jsonify, session
from models import get_db
import psycopg2.extras

bp = Blueprint('notifications', __name__)


def current_user_id():
    return session.get('user_id')

def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def create_notification(user_id, type_, actor_id, target_id=None):
    """Cria uma notificação, exceto se o usuário estiver notificando a si mesmo."""
    if user_id == actor_id:
        return
    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        INSERT INTO notifications (user_id, type, actor_id, target_id)
        VALUES (%s, %s, %s, %s)
    """, (user_id, type_, actor_id, target_id))
    conn.commit()
    conn.close()


@bp.route('/notifications')
def list_notifications():
    uid = current_user_id()
    if not uid:
        return jsonify([])

    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT
            n.id, n.type, n.target_id, n.is_read, n."createdAt",
            u.id AS actor_id, u.username AS actor_username, u.avatar AS actor_avatar
        FROM notifications n
        JOIN users u ON u.id = n.actor_id
        WHERE n.user_id = %s
        ORDER BY n."createdAt" DESC
        LIMIT 30
    """, (uid,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    for r in rows:
        r['actor_avatar'] = r['actor_avatar'] or 'img/default.png'

    return jsonify(rows)


@bp.route('/notifications/unread_count')
def unread_count():
    uid = current_user_id()
    if not uid:
        return jsonify({'count': 0})

    conn = get_db()
    c    = _cursor(conn)
    c.execute("SELECT COUNT(*) AS cnt FROM notifications WHERE user_id=%s AND is_read=0", (uid,))
    count = c.fetchone()['cnt']
    conn.close()

    return jsonify({'count': count})


@bp.route('/notifications/mark_read', methods=['POST'])
def mark_read():
    uid = current_user_id()
    if not uid:
        return jsonify({'error': 'not_logged_in'}), 401

    conn = get_db()
    c    = _cursor(conn)
    c.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s AND is_read=0", (uid,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})