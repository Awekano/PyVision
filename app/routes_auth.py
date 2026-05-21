from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from .models import User
from .services.audit import audit

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("login.html")

@auth_bp.post("/login")
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        audit("login_failed", username=username or None)
        flash("Erreur identifiant ou mot de passe invalide", "error")
        return redirect(url_for("auth.login"))

    login_user(user)
    audit("login_success", username=user.username)
    return redirect(url_for("main.index"))

@auth_bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        audit("logout", username=current_user.username)
    logout_user()
    return redirect(url_for("auth.login"))
