from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from models import get_db
import psycopg2.extras
import secrets
import smtplib
import os
from email.mime.text import MIMEText
from datetime import datetime, timedelta

bp = Blueprint('auth', __name__)


def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Registro ──────────────────────────────────────────────────────────────────

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    data     = request.get_json(silent=True) or request.form
    username = data.get('username')
    email    = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        if request.content_type != 'application/json':
            return render_template('register.html', error="Preencha todos os campos")
        return jsonify({'error': 'Todos os campos são obrigatórios'}), 400

    conn = get_db()
    c    = _cursor(conn)
    try:
        c.execute(
            'INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
            (username, email, generate_password_hash(password))
        )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        if request.content_type != 'application/json':
            return render_template('register.html', error="Usuário ou e-mail já cadastrado")
        return jsonify({'error': 'Usuário ou e-mail já cadastrado'}), 400

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
    c    = _cursor(conn)
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


# ── Helper: envio de e-mail ───────────────────────────────────────────────────

def send_reset_email(to_email, token):
    mail_user = os.environ.get('MAIL_USERNAME')
    mail_pass = os.environ.get('MAIL_PASSWORD')

    if not mail_user or not mail_pass:
        print(f"[DEV] Link de recuperação para {to_email}: /reset-password/{token}")
        return False

    reset_url = f"{os.environ.get('APP_URL', 'http://localhost:5000')}/reset-password/{token}"

    body = f"""Olá!

Você solicitou a recuperação de senha no Soundtrackr.

Clique no link abaixo para criar uma nova senha (válido por 1 hora):

{reset_url}

Se você não solicitou isso, ignore este e-mail.

— Soundtrackr
"""

    msg = MIMEText(body)
    msg['Subject'] = 'Recuperação de senha — Soundtrackr'
    msg['From']    = mail_user
    msg['To']      = to_email

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(mail_user, mail_pass)
            server.sendmail(mail_user, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False


# ── Esqueci a senha ───────────────────────────────────────────────────────────

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')

    email = request.form.get('email', '').strip()

    conn = get_db()
    c    = _cursor(conn)
    c.execute('SELECT id, username FROM users WHERE email=%s', (email,))
    user = c.fetchone()

    if user:
        token      = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)

        c.execute(
            'INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s)',
            (user['id'], token, expires_at)
        )
        conn.commit()
        send_reset_email(email, token)

    conn.close()

    # Sempre mostra a mesma mensagem, existindo o e-mail ou não (segurança)
    return render_template('forgot_password.html', success=True)


# ── Redefinir senha ───────────────────────────────────────────────────────────

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db()
    c    = _cursor(conn)
    c.execute("""
        SELECT * FROM password_resets
        WHERE token=%s AND used=0 AND expires_at > NOW()
    """, (token,))
    reset_row = c.fetchone()

    if not reset_row:
        conn.close()
        return render_template('reset_password.html', invalid=True)

    if request.method == 'GET':
        conn.close()
        return render_template('reset_password.html', token=token)

    password = request.form.get('password', '')
    if len(password) < 4:
        conn.close()
        return render_template('reset_password.html', token=token, error="Senha muito curta")

    c.execute(
        'UPDATE users SET password=%s WHERE id=%s',
        (generate_password_hash(password), reset_row['user_id'])
    )
    c.execute('UPDATE password_resets SET used=1 WHERE token=%s', (token,))
    conn.commit()
    conn.close()

    return redirect(url_for('auth.login'))