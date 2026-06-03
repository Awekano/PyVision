# app/routes_main.py
# Ce fichier contient les routes principales du site PyVision
# Il gère l'accueil, les événements, le live, les enregistrements et l'administration

import mimetypes
import os
import time as time_module
from datetime import datetime, time as dt_time
from pathlib import Path

import cv2
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    stream_with_context,
    url_for,
    send_from_directory,
)
from flask_login import current_user, login_required
from sqlalchemy import text
from werkzeug.utils import secure_filename

from app import db
from app.models import AlertSettings, AuditLog, Event, User
from app.services.alert_settings import is_alert_allowed
from app.services.audit import audit
from mailer import send_alert_email
from functools import wraps

# Création du blueprint principal
main_bp = Blueprint("main", __name__)

# Extensions vidéo autorisées dans le projet
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".avi", ".mov"}

# Extensions qui peuvent être affichées directement dans le navigateur
INLINE_VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov"}

# Extensions acceptées lors de l'envoi d'une vidéo depuis la webcam
UPLOAD_EXT = {".webm", ".mp4", ".mkv"}

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Bloque l'accès si l'utilisateur n'est pas administrateur
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@main_bp.get("/")
@login_required
def index():
    # Affiche la page d'accueil après connexion
    return render_template("index.html")


@main_bp.get("/events")
@login_required
def events():
    # Récupère le type d'événement demandé dans l'URL
    kind = request.args.get("kind")

    # Prépare la requête des événements, du plus récent au plus ancien
    q = Event.query.order_by(Event.created_at.desc())

    # Applique un filtre si le type d'événement est valide
    if kind in ("detection", "alarme", "alerte", "alert", "video_recorded"):
        q = q.filter_by(kind=kind)

    # Limite l'affichage aux 200 derniers événements
    rows = q.limit(200).all()

    # Ajoute l'action dans le journal de bord
    audit("view_events", username=current_user.username)

    # Affiche la page des événements
    return render_template("events.html", events=rows, selected_kind=kind)


@main_bp.get("/audit")
@login_required
def audit_logs():
    # Seuls les administrateurs peuvent consulter le journal de bord
    if getattr(current_user, "role", None) != "admin":
        abort(403)

    # Récupère les 200 dernières actions
    rows = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()

    # Ajoute l'action dans le journal de bord
    audit("view_audit", username=current_user.username)

    # Affiche la page d'audit
    return render_template("audit.html", audits=rows)


@main_bp.get("/live")
@login_required
def live():
    # Ajoute l'accès au live dans le journal de bord
    audit("view_live", username=current_user.username)

    # Affiche la page du live caméra
    return render_template("live.html")


@main_bp.get("/live_feed")
@login_required
def live_feed():
    # Récupère l'URL RTSP de la caméra depuis la configuration
    rtsp_url = current_app.config.get("RTSP_URL")

    # Si aucune caméra n'est configurée, retourne une erreur
    if not rtsp_url:
        audit("live_feed_missing_rtsp_url", username=current_user.username)
        return Response("RTSP_URL non configurée", status=500, mimetype="text/plain")

    # Ajoute l'ouverture du flux dans le journal de bord
    audit("open_live_feed", username=current_user.username)

    # Retourne le flux vidéo au format MJPEG
    return Response(
        stream_with_context(_mjpeg_stream(rtsp_url)),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@main_bp.get("/download/<int:event_id>")
@login_required
def download(event_id: int):
    # Récupère l'événement demandé ou retourne une erreur 404
    ev = Event.query.get_or_404(event_id)

    # Si aucun fichier vidéo n'est associé, retourne une erreur
    if not ev.video_path:
        abort(404)

    # Récupère le dossier des enregistrements
    base_dir = _recordings_dir()

    # Construit le chemin absolu de la vidéo
    if os.path.isabs(ev.video_path):
        abs_path = os.path.abspath(ev.video_path)
    else:
        abs_path = os.path.abspath(os.path.join(base_dir, ev.video_path))

    # Sécurité : empêche de sortir du dossier recordings
    if not abs_path.startswith(base_dir + os.sep):
        abort(403)

    # Vérifie que le fichier existe
    if not os.path.isfile(abs_path):
        abort(404)

    # Ajoute le téléchargement dans le journal de bord
    audit(f"download_video:{event_id}", username=current_user.username)

    # Envoie le fichier en téléchargement
    return send_file(abs_path, as_attachment=True, conditional=True)


def _recordings_dir() -> str:
    # Retourne le chemin absolu du dossier recordings
    return os.path.abspath(os.path.join(current_app.root_path, "..", "recordings"))


@main_bp.get("/recordings")
@login_required
def recordings():
    # Récupère le dossier des enregistrements
    base_dir = _recordings_dir()
    rows = []

    # Si le dossier recordings n'existe pas, affiche une erreur propre
    if not os.path.isdir(base_dir):
        audit(
            "view_recordings_folder_missing",
            username=current_user.username,
            extra={"dir": base_dir},
        )
        return render_template(
            "recordings.html",
            rows=[],
            error=f"Dossier introuvable : {base_dir}",
        )

    # Parcours des fichiers dans le dossier recordings
    for root, _, files in os.walk(base_dir):
        for name in files:
            ext = os.path.splitext(name)[1].lower()

            # Ignore les fichiers qui ne sont pas des vidéos
            if ext not in VIDEO_EXT:
                continue

            # Création du chemin absolu du fichier
            abs_path = os.path.abspath(os.path.join(root, name))

            # Sécurité : empêche de sortir du dossier recordings
            if not abs_path.startswith(base_dir + os.sep):
                continue

            # Récupération des informations du fichier
            st = os.stat(abs_path)
            rel_path = os.path.relpath(abs_path, base_dir).replace("\\", "/")

            # Ajout de la vidéo dans la liste affichée
            rows.append(
                {
                    "rel_path": rel_path,
                    "name": name,
                    "ext": ext,
                    "size": st.st_size,
                    "size_mb": round(st.st_size / (1024 * 1024), 2),
                    "dt": datetime.fromtimestamp(st.st_mtime),
                    "can_preview": ext in INLINE_VIDEO_EXT,
                }
            )

    # Trie les vidéos de la plus récente à la plus ancienne
    rows.sort(key=lambda r: r["dt"], reverse=True)

    # Ajoute l'action dans le journal de bord
    audit(
        "view_recordings_folder",
        username=current_user.username,
        extra={"count": len(rows)},
    )

    # Affiche la page des enregistrements
    return render_template("recordings.html", rows=rows, error=None)


@main_bp.get("/recordings/view/<path:rel_path>")
@login_required
def recordings_view(rel_path: str):
    # Récupère le chemin absolu du fichier demandé
    base_dir = _recordings_dir()
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))

    # Sécurité : empêche de lire un fichier en dehors de recordings
    if not abs_path.startswith(base_dir + os.sep):
        abort(403)

    # Vérifie que le fichier existe
    if not os.path.isfile(abs_path):
        abort(404)

    # Détermine le type MIME du fichier
    ext = os.path.splitext(abs_path)[1].lower()
    guessed_mime = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"

    # Indique si la vidéo peut être ouverte directement dans le navigateur
    inline = ext in INLINE_VIDEO_EXT

    # Ajoute la consultation dans le journal de bord
    audit(
        "view_recording_file",
        username=current_user.username,
        extra={"file": rel_path},
    )

    # Envoie la vidéo au navigateur
    return send_file(
        abs_path,
        mimetype=guessed_mime,
        as_attachment=not inline,
        conditional=True,
        etag=True,
        last_modified=os.path.getmtime(abs_path),
        max_age=0,
    )


@main_bp.get("/recordings/download/<path:rel_path>")
@login_required
def recordings_download(rel_path: str):
    # Récupère le chemin absolu du fichier demandé
    base_dir = _recordings_dir()
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))

    # Sécurité : empêche de télécharger un fichier en dehors de recordings
    if not abs_path.startswith(base_dir + os.sep):
        abort(403)

    # Vérifie que le fichier existe
    if not os.path.isfile(abs_path):
        abort(404)

    # Ajoute le téléchargement dans le journal de bord
    audit(
        "download_recording_file",
        username=current_user.username,
        extra={"file": rel_path},
    )

    # Envoie le fichier en téléchargement
    return send_file(abs_path, as_attachment=True, conditional=True)


def _mjpeg_stream(rtsp_url: str):
    # Récupère le mode de transport RTSP
    transport = current_app.config.get("RTSP_TRANSPORT", "tcp").lower()

    # Récupère la qualité JPEG configurée
    jpeg_quality = int(current_app.config.get("MJPEG_QUALITY", 80))

    # Prépare les options OpenCV pour le flux RTSP
    options = []

    # Force le transport TCP si configuré
    if transport == "tcp":
        options.append("rtsp_transport;tcp")

    # Ajoute les options dans les variables d'environnement OpenCV
    if options:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "|".join(options)

    # Ouverture du flux vidéo RTSP
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

    # Si le flux est inaccessible, affiche une image d'erreur
    if not cap.isOpened():
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + _error_frame("Flux RTSP inaccessible")
            + b"\r\n"
        )
        return

    # Paramètre de qualité JPEG
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]

    try:
        # Boucle de lecture du flux caméra
        while True:
            ok, frame = cap.read()

            # Si aucune image n'est lue, attend un peu puis recommence
            if not ok or frame is None:
                time_module.sleep(0.2)
                continue

            # Encode l'image en JPEG
            success, buffer = cv2.imencode(".jpg", frame, encode_params)

            # Si l'encodage échoue, on ignore l'image
            if not success:
                continue

            # Envoie l'image au navigateur au format MJPEG
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )
    finally:
        # Ferme proprement le flux caméra
        cap.release()


def _error_frame(text_value: str) -> bytes:
    # Cette fonction crée une image noire avec un message d'erreur
    import numpy as np

    # Création d'une image noire
    frame = np.zeros((480, 854, 3), dtype=np.uint8)

    # Ajout du texte sur l'image
    cv2.putText(
        frame,
        text_value,
        (30, 240),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    # Encodage de l'image en JPEG
    ok, buffer = cv2.imencode(".jpg", frame)

    # Retourne l'image encodée
    return buffer.tobytes() if ok else b""

@main_bp.post("/recordings/delete/<path:rel_path>")
@login_required
def recordings_delete(rel_path: str):
    # Supprime un fichier vidéo depuis la page Enregistrements
    # Supprime aussi l'événement associé dans la base de données

    try:
        # Récupère le dossier des enregistrements
        base_dir = _recordings_dir()

        # Construit le chemin absolu du fichier demandé
        abs_path = os.path.abspath(os.path.join(base_dir, rel_path))

        # Sécurité : empêche de sortir du dossier recordings
        if not abs_path.startswith(base_dir + os.sep):
            abort(403)

        # Vérifie que le fichier est bien une vidéo autorisée
        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in VIDEO_EXT:
            abort(403)

        # Récupère le nom du fichier seul
        filename = os.path.basename(rel_path)

        # Supprime le fichier vidéo s'il existe
        if os.path.isfile(abs_path):
            os.remove(abs_path)

        # Cherche les événements liés à cette vidéo
        linked_events = Event.query.filter(
            db.or_(
                Event.video_path == rel_path,
                Event.video_path == filename
            )
        ).all()

        # Supprime les événements trouvés
        deleted_events = 0
        for event in linked_events:
            db.session.delete(event)
            deleted_events += 1

        # Valide les suppressions en base
        db.session.commit()

        # Ajoute l'action dans le journal de bord
        try:
            audit(
                "delete_recording_file",
                username=current_user.username,
                extra={
                    "file": rel_path,
                    "deleted_events": deleted_events
                },
            )
        except Exception as audit_error:
            current_app.logger.error(f"Erreur audit delete_recording_file: {audit_error}")

        flash("Enregistrement et événement associé supprimés avec succès", "success")
        return redirect(url_for("main.recordings"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Erreur recordings_delete")
        flash(f"Erreur lors de la suppression : {e}", "danger")
        return redirect(url_for("main.recordings"))

@main_bp.post("/upload_webcam_recording")
@login_required
def upload_webcam_recording():
    # Cette route reçoit une vidéo envoyée par le mode webcam démo
    try:
        # Récupère le fichier vidéo envoyé par le navigateur
        file = request.files.get("video")

        # Vérifie qu'un fichier a bien été reçu
        if not file:
            return jsonify({"error": "Aucun fichier reçu"}), 400

        # Sécurise le nom original du fichier
        original_name = secure_filename(file.filename or "")

        # Récupère l'extension du fichier
        ext = Path(original_name).suffix.lower()

        # Vérifie que l'extension est autorisée
        if ext not in UPLOAD_EXT:
            return jsonify({"error": f"Extension non autorisée : {ext}"}), 400

        # Crée le dossier recordings si besoin
        recordings_dir = _recordings_dir()
        os.makedirs(recordings_dir, exist_ok=True)

        # Génère un nom de fichier unique avec la date et l'utilisateur
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"motion_demo_{current_user.username}_{timestamp}{ext}"
        save_path = os.path.join(recordings_dir, filename)

        # Sauvegarde la vidéo sur le serveur
        file.save(save_path)

        # Chemin relatif stocké dans la base
        rel_path = filename

        # Vérifie si l'alerte mail doit être envoyée
        is_alert = is_alert_allowed()

        # Définit le type d'événement selon la plage horaire
        event_kind = "alerte" if is_alert else "video_recorded"

        # Description affichée dans la base
        description = "Alerte mail envoyée" if is_alert else "Vidéo enregistrée"

        # Création de l'événement avec les colonnes du modèle SQLAlchemy
        event = Event(
            kind=event_kind,
            video_path=rel_path,
            screenshot_path=None,
        )

        # Ajout de l'événement dans la session
        db.session.add(event)

        # Flush pour récupérer l'ID avant le commit
        db.session.flush()

        # Mise à jour des colonnes supplémentaires de la table events
        db.session.execute(
            text(
                """
                UPDATE events
                SET event_type = :event_type,
                    camera_name = :camera_name,
                    description = :description,
                    video_filename = :video_filename,
                    image_filename = :image_filename,
                    kind = :kind,
                    screenshot_path = :screenshot_path,
                    video_path = :video_path
                WHERE id = :event_id
                """
            ),
            {
                "event_type": event_kind,
                "camera_name": "Camera 1",
                "description": description,
                "video_filename": filename,
                "image_filename": None,
                "kind": event_kind,
                "screenshot_path": None,
                "video_path": rel_path,
                "event_id": event.id,
            },
        )

        # Validation en base de données
        db.session.commit()

        # Envoi du mail si l'événement est une alerte
        if is_alert:
            try:
                send_alert_email(rel_path, "alerte")
            except Exception as e:
                current_app.logger.error(f"Erreur envoi mail : {e}")
        else:
            current_app.logger.info(
                "Alerte mail non envoyée : hors plage horaire ou désactivée"
            )

        # Ajout de l'action dans le journal de bord
        try:
            audit(
                "upload_webcam_recording",
                username=current_user.username,
                extra={"file": filename, "event_id": event.id, "kind": event_kind},
            )
        except Exception as audit_error:
            current_app.logger.error(f"Erreur audit upload_webcam_recording: {audit_error}")

        # Réponse JSON envoyée au navigateur
        return jsonify(
            {
                "message": "Vidéo enregistrée",
                "filename": filename,
                "event_id": event.id,
                "type": event_kind,
            }
        ), 201

    except Exception as e:
        # Annule les changements en base en cas d'erreur
        db.session.rollback()

        # Log de l'erreur
        current_app.logger.exception("Erreur upload_webcam_recording")

        # Retourne l'erreur au navigateur
        return jsonify({"error": str(e)}), 500


@main_bp.post("/events/delete/<int:event_id>")
@login_required
def delete_event(event_id):
    # Cette route supprime un événement et sa vidéo associée
    try:
        # Récupère l'événement ou retourne une erreur 404
        event = Event.query.get_or_404(event_id)

        # Si une vidéo est associée à l'événement
        if event.video_path:
            base_dir = _recordings_dir()
            abs_path = os.path.abspath(os.path.join(base_dir, event.video_path))

            # Supprime la vidéo uniquement si elle est dans le dossier recordings
            if abs_path.startswith(base_dir + os.sep) and os.path.exists(abs_path):
                os.remove(abs_path)

        # Supprime l'événement de la base
        db.session.delete(event)

        # Valide la suppression
        db.session.commit()

        # Ajoute la suppression dans le journal de bord
        try:
            audit("delete_event", username=current_user.username)
        except Exception as audit_error:
            current_app.logger.error(f"Erreur audit delete_event: {audit_error}")

        # Retourne à la page événements
        return redirect(url_for("main.events"))

    except Exception as e:
        # Annule la suppression en cas d'erreur
        db.session.rollback()

        # Log de l'erreur
        current_app.logger.exception("Erreur delete_event")

        # Affiche l'erreur
        return f"Erreur suppression : {e}", 500


@main_bp.route("/admin/alert-settings", methods=["GET", "POST"])
@login_required
def alert_settings():
    # Cette page permet à l'admin de configurer les horaires d'alerte mail

    # Vérifie que l'utilisateur est administrateur
    if getattr(current_user, "role", None) != "admin":
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))

    # Récupère les paramètres existants
    settings = AlertSettings.query.first()

    # Crée des paramètres par défaut s'ils n'existent pas
    if not settings:
        settings = AlertSettings(
            enabled=True,
            start_time=dt_time(22, 0),
            end_time=dt_time(6, 0),
        )
        db.session.add(settings)
        db.session.commit()

    # Si le formulaire est envoyé
    if request.method == "POST":
        # Active ou désactive l'alerte
        settings.enabled = request.form.get("enabled") == "on"

        # Met à jour l'heure de début
        settings.start_time = dt_time.fromisoformat(request.form.get("start_time"))

        # Met à jour l'heure de fin
        settings.end_time = dt_time.fromisoformat(request.form.get("end_time"))

        # Enregistre les paramètres
        db.session.commit()

        # Message de confirmation
        flash("Paramètres d'alerte mis à jour", "success")

        # Recharge la page
        return redirect(url_for("main.alert_settings"))

    # Affiche la page des paramètres
    return render_template("alert_settings.html", settings=settings)


@main_bp.route("/mindview")
def mindview():
    # Affiche la page de téléchargement du Gantt MindView
    return render_template("mindview.html")


@main_bp.route("/mindview/download")
def download_mindview():
    # Chemin du fichier MindView sur le serveur
    file_path = "/home/enzo/eryma_web/app/static/downloads/PyVision_gantt.mvdx"

    # Vérifie que le fichier existe
    if not os.path.isfile(file_path):
        return f"Fichier introuvable : {file_path}", 404

    # Envoie le fichier en téléchargement
    return send_file(
        file_path,
        as_attachment=True,
        download_name="PyVision_gantt.mvdx",
        mimetype="application/octet-stream"
    )
@main_bp.route("/admin/users")
@login_required
@admin_required
def admin_users():
    # Affiche la liste des utilisateurs
    users = User.query.order_by(User.id.asc()).all()
    return render_template("admin_users.html", users=users)


@main_bp.route("/admin/users/add", methods=["POST"])
@login_required
@admin_required
def admin_add_user():
    # Récupère les champs du formulaire
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    is_admin = request.form.get("is_admin") == "on"

    # Vérifie que les champs obligatoires sont remplis
    if not username or not password:
        flash("Le nom d'utilisateur et le mot de passe sont obligatoires", "error")
        return redirect(url_for("main.admin_users"))

    # Vérifie si le nom d'utilisateur existe déjà
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash("Cet utilisateur existe déjà", "error")
        return redirect(url_for("main.admin_users"))

    # Crée le nouvel utilisateur
    new_user = User(
        username=username,
        role="admin" if is_admin else "user",
        is_active=True
    )

    # Hash le mot de passe avant l'enregistrement
    new_user.set_password(password)

    # Enregistre dans la base de données
    db.session.add(new_user)
    db.session.commit()

    flash("Utilisateur ajouté avec succès", "success")
    return redirect(url_for("main.admin_users"))


@main_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    # Récupère l'utilisateur demandé
    user = User.query.get_or_404(user_id)

    # Empêche l'admin connecté de supprimer son propre compte
    if user.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte", "error")
        return redirect(url_for("main.admin_users"))

    # Supprime le compte utilisateur
    db.session.delete(user)
    db.session.commit()

    flash("Utilisateur supprimé avec succès", "success")
    return redirect(url_for("main.admin_users"))
