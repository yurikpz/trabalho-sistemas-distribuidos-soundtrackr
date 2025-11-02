from flask import Flask
from flask_cors import CORS
import os

from models import get_db, init_db

# INICIALIZA O BD
init_db()

#CRIAÇÃO DO APP
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'super-secret-key'
CORS(app)

app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Importar rotas depois do app existir
from routes import auth, profile, library, integrations, views
from profile_public import bp as public_profile_bp  

# REGISTRA BLUEPRINTS
app.register_blueprint(auth.bp)
app.register_blueprint(profile.bp)
app.register_blueprint(library.bp)
app.register_blueprint(integrations.bp)
app.register_blueprint(views.bp)
app.register_blueprint(public_profile_bp)  

#RUN
if __name__ == '__main__':
    app.run(debug=True)
