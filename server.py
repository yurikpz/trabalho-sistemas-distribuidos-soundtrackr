import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from flask_cors import CORS
from models import get_db, init_db
from routes import auth, profile, library, integrations, views, social, collection, notifications, interactions
init_db()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-troque-em-producao')
CORS(app)

app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

from routes import auth, profile, library, integrations, views, social
from profile_public import bp as public_profile_bp
from routes import auth, profile, library, integrations, views, social, collection

app.register_blueprint(collection.bp)
app.register_blueprint(auth.bp)
app.register_blueprint(profile.bp)
app.register_blueprint(library.bp)
app.register_blueprint(integrations.bp)
app.register_blueprint(views.bp)
app.register_blueprint(social.bp)       # novo
app.register_blueprint(public_profile_bp)
app.register_blueprint(notifications.bp)
app.register_blueprint(interactions.bp)

if __name__ == '__main__':
    app.run(debug=True)