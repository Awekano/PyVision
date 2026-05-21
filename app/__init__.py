from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv
from pathlib import Path

# Chemin ABSOLU vers .env (fiable)
BASE_DIR = Path(__file__).resolve().parent.parent   # -> /home/enzo/eryma_web
load_dotenv(BASE_DIR / ".env")
from .config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from .routes_auth import auth_bp
    from .routes_main import main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        from . import models
        db.create_all()

    return app
