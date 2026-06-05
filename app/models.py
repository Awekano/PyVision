# app/models.py
# Ce fichier définit les modèles de données utilisés par SQLAlchemy
# Chaque classe représente une table dans la base de données

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager


class User(UserMixin, db.Model):
    # Table des utilisateurs du site web
    __tablename__ = "users"

    # Identifiant unique de l'utilisateur
    id = db.Column(db.Integer, primary_key=True)

    # Nom d'utilisateur
    username = db.Column(db.String(80), unique=True, nullable=False)

    # Mot de passe hashé
    password_hash = db.Column(db.String(255), nullable=False)

    # Rôle de l'utilisateur : user ou admin
    role = db.Column(db.String(20), default="user", nullable=False)

    # Permet de désactiver un compte sans le supprimer définitivement
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, raw_password: str) -> None:
        # Hash le mot de passe avant de l'enregistrer
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        # Vérifie si le mot de passe donné correspond au hash enregistré
        return check_password_hash(self.password_hash, raw_password)

    def is_admin(self) -> bool:
        # Retourne True si l'utilisateur est administrateur
        return self.role == "admin"

class Event(db.Model):
    # Table des événements caméra
    __tablename__ = "events"

    # Identifiant unique de l'événement
    id = db.Column(db.Integer, primary_key=True)

    # Type d'événement : alerte, détection, vidéo enregistrée
    kind = db.Column(db.String(30), nullable=False)

    # Date et heure de création de l'événement
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Chemin vers une capture d'écran si disponible
    screenshot_path = db.Column(db.String(255), nullable=True)

    # Chemin vers la vidéo enregistrée si disponible
    video_path = db.Column(db.String(255), nullable=True)


class AuditLog(db.Model):
    # Table du journal de bord
    __tablename__ = "audit_logs"

    # Identifiant unique de la ligne d'audit
    id = db.Column(db.Integer, primary_key=True)

    # Date et heure de l'action
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Utilisateur concerné par l'action
    username = db.Column(db.String(80), nullable=True)

    # Action réalisée
    action = db.Column(db.String(120), nullable=False)

    # Adresse IP de l'utilisateur
    ip = db.Column(db.String(64), nullable=True)

    # Navigateur ou client utilisé
    user_agent = db.Column(db.String(255), nullable=True)


class AlertSettings(db.Model):
    # Table des paramètres d'alerte mail
    __tablename__ = "alert_settings"

    # Identifiant unique des paramètres
    id = db.Column(db.Integer, primary_key=True)

    # Active ou désactive les alertes
    enabled = db.Column(db.Boolean, default=True)

    # Heure de début de la plage d'alerte
    start_time = db.Column(db.Time, nullable=False)

    # Heure de fin de la plage d'alerte
    end_time = db.Column(db.Time, nullable=False)

class AppSetting(db.Model):
    # Nom de la table utilisée dans la base de données
    __tablename__ = "app_settings"

    # Identifiant unique du paramètre
    id = db.Column(db.Integer, primary_key=True)

    # Nom du paramètre, par exemple : alert_email_recipient
    setting_key = db.Column(db.String(100), unique=True, nullable=False)

    # Valeur du paramètre, par exemple : destinataire@mail.com
    setting_value = db.Column(db.String(255), nullable=False)

@login_manager.user_loader
def load_user(user_id: str):
    # Recharge l'utilisateur connecté à partir de son ID
    return db.session.get(User, int(user_id))
