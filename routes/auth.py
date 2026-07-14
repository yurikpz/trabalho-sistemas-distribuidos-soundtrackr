from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from models import get_db
import psycopg2.extras

bp = Blueprint('auth', __name__)


# ── Registro ──────────────────────────────────────────────────────────────────

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    data     = request.get_json(silent=True) or request.form
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        if request.content_type != 'application/json':
            return render_template('register.html', error="Usuário e senha são obrigatórios")
        return jsonify({'error': 'Usuário e senha obrigatórios'}), 400

    conn = get_db()
    c    = conn.cursor()
    try:
        c.execute(
            'INSERT INTO users (username, password) VALUES (%s, %s)',
            (username, generate_password_hash(password))
        )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        if request.content_type != 'application/json':
            return render_template('register.html', error="Usuário já existe")
        return jsonify({'error': 'Usuário já existe'}), 400

    conn.close()
    if request.content_type != 'application/json':
        return redirect(url_for('auth.login'))
    return jsonify({'success': True, 'message': 'Registrado com sucesso'})


# ── Login ─────────────────────────────────────────────────────────────────────

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    data     = request.get_json(silent=True) or request.form
    username = data.get('username')
    password = data.get('password')

    conn = get_db()
    c    = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute('SELECT * FROM users WHERE username=%s', (username,))
    user = c.fetchone()
    conn.close()

    if user and check_password_hash(user['password'], password):
        session['user_id']  = user['id']
        session['username'] = user['username']
        if request.content_type != 'application/json':
            return redirect(url_for('views.landing'))
        return jsonify({'success': True, 'redirect': '/landing'})

    if request.content_type != 'application/json':
        return render_template('login.html', error="Usuário ou senha inválidos")
    return jsonify({'error': 'Usuário ou senha inválidos'}), 400


# ── Logout ────────────────────────────────────────────────────────────────────

@bp.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    if request.content_type != 'application/json':
        return redirect(url_for('auth.login'))
    return jsonify({'success': True})