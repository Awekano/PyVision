# app/routes_auth.py
# Ce fichier gère la connexion et la déconnexion des utilisateurs

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from .models import User
from .services.audit import audit

# Création du blueprint auth avec le préfixe /auth
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.get("/login")
def login():
    # Si l'utilisateur est déjà connecté, il est redirigé vers l'accueil
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    # Affichage de la page de connexion
    return render_template("login.html")


@auth_bp.post("/login")
def login_post():
    # Récupération de l'identifiant et du mot de passe depuis le formulaire
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    # Recherche de l'utilisateur dans la base
    user = User.query.filter_by(username=username).first()

    # Vérification de l'identifiant et du mot de passe
    if not user or not user.check_password(password):
        audit("login_failed", username=username or None)
        flash("Erreur identifiant ou mot de passe invalide", "error")
        return redirect(url_for("auth.login"))

    # Connexion de l'utilisateur
    login_user(user)

    # Ajout de l'action dans le journal de bord
    audit("login_success", username=user.username)

    # Redirection vers l'accueil
    return redirect(url_for("main.index"))


@auth_bp.post("/logout")
def logout():
    # Ajout de la déconnexion dans le journal de bord
    if current_user.is_authenticated:
        audit("logout", username=current_user.username)

    # Déconnexion de l'utilisateur
    logout_user()

    # Retour à la page de connexion
    return redirect(url_for("auth.login"))
