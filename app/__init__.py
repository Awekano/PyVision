# app/__init__.py
# Ce fichier initialise l'application Flask, la base de données et la connexion utilisateur

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv
from pathlib import Path

# Chemin absolu vers le dossier principal du projet
BASE_DIR = Path(__file__).resolve().parent.parent

# Chargement du fichier .env
load_dotenv(BASE_DIR / ".env")

from .config import Config

# Initialisation de SQLAlchemy pour gérer la base de données
db = SQLAlchemy()

# Initialisation de Flask-Login pour gérer les connexions utilisateur
login_manager = LoginManager()

# Route utilisée lorsqu'un utilisateur non connecté tente d'accéder à une page protégée
login_manager.login_view = "auth.login"


def create_app():
    # Création de l'application Flask
    app = Flask(__name__)

    # Chargement de la configuration du projet
    app.config.from_object(Config)

    # Liaison de la base de données avec l'application
    db.init_app(app)

    # Liaison de Flask-Login avec l'application
    login_manager.init_app(app)

    # Import des routes d'authentification
    from .routes_auth import auth_bp

    # Import des routes principales du site
    from .routes_main import main_bp

    # Enregistrement des routes d'authentification
    app.register_blueprint(auth_bp)

    # Enregistrement des routes principales
    app.register_blueprint(main_bp)

    # Création des tables si elles n'existent pas
    with app.app_context():
        from . import models
        db.create_all()

    # Retourne l'application prête à être utilisée
    return app
