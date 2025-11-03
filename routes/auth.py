from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from models import get_db

bp = Blueprint('auth', __name__)

#REGISTRO DE USUÁRIO
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    #aceita tanto JSON (fetch) quanto FORM (HTML)
    data = request.get_json(silent=True) or request.form
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        #Se veio via formulário = renderiza a página com erro
        if request.content_type != 'application/json':
            return render_template('register.html', error="Usuário e senha são obrigatórios")
        # Se veio via JS = responde JSON
        return jsonify({'error': 'Usuário e senha obrigatórios'}), 400

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                  (username, generate_password_hash(password)))
        conn.commit()
    except Exception:
        conn.close()
        if request.content_type != 'application/json':
            return render_template('register.html', error="Usuário já existe")
        return jsonify({'error': 'Usuário já existe'}), 400

    conn.close()
    #Se veio via form = redireciona pro login
    if request.content_type != 'application/json':
        return redirect(url_for('auth.login'))
    #Se veio via fetch = retorna JSON
    return jsonify({'success': True, 'message': 'Registrado com sucesso'})



# LOGIN

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    data = request.get_json(silent=True) or request.form
    username = data.get('username')
    password = data.get('password')

    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username=?', (username,))
    user = c.fetchone()
    conn.close()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        #FORM = redireciona
        if request.content_type != 'application/json':
            return redirect(url_for('views.landing'))
        #FETCH = retorna JSON
        return jsonify({'success': True, 'redirect': '/landing'})

    #usuário ou senha incorretos
    if request.content_type != 'application/json':
        return render_template('login.html', error="Usuário ou senha inválidos")
    return jsonify({'error': 'Usuário ou senha inválidos'}), 400



#LOGOUT

@bp.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    #se for chamado via botão no site
    if request.content_type != 'application/json':
        return redirect(url_for('auth.login'))
    return jsonify({'success': True})
