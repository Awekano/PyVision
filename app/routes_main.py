# app/routes_main.py
# Ce fichier contient les routes principales du site PyVision
# Il gère l'accueil, les événements, le live, les enregistrements et l'administration

import mimetypes
import os
import time as time_module
from datetime import datetime, time as dt_time
from functools import wraps

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
)
from flask_login import current_user, login_required

from app import db
from app.models import AlertSettings, AuditLog, Event, User
from app.services.audit import audit


main_bp = Blueprint("main", __name__)

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
INLINE_VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov"}


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


@main_bp.get("/")
@login_required
def index():
    return render_template("index.html")


@main_bp.get("/events")
@login_required
def events():
    kind = request.args.get("kind")

    q = Event.query.order_by(Event.created_at.desc())

    if kind in ("detection", "alarme", "alerte", "alert", "video_recorded", "motion"):
        q = q.filter_by(kind=kind)

    rows = q.limit(200).all()

    audit("view_events", username=current_user.username)

    return render_template("events.html", events=rows, selected_kind=kind)


@main_bp.get("/audit")
@login_required
def audit_logs():
    if getattr(current_user, "role", None) != "admin":
        abort(403)

    rows = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()

    audit("view_audit", username=current_user.username)

    return render_template("audit.html", audits=rows)


@main_bp.get("/live")
@login_required
def live():
    audit("view_live", username=current_user.username)
    return render_template("live.html")


@main_bp.get("/live_feed")
@login_required
def live_feed():
    rtsp_url = current_app.config.get("RTSP_URL")

    if not rtsp_url:
        audit("live_feed_missing_rtsp_url", username=current_user.username)
        return Response("RTSP_URL non configurée", status=500, mimetype="text/plain")

    audit("open_live_feed", username=current_user.username)

    return Response(
        stream_with_context(_mjpeg_stream(rtsp_url)),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@main_bp.get("/detection_status")
@login_required
def detection_status():
    latest_event = Event.query.order_by(Event.created_at.desc()).first()

    return jsonify(
        {
            "service": "server",
            "recording_mode": "server",
            "latest_event": {
                "id": latest_event.id,
                "kind": latest_event.kind,
                "video_path": latest_event.video_path,
                "created_at": latest_event.created_at.strftime("%d/%m/%Y %H:%M:%S"),
            }
            if latest_event
            else None,
        }
    )


@main_bp.get("/download/<int:event_id>")
@login_required
def download(event_id: int):
    ev = Event.query.get_or_404(event_id)

    if not ev.video_path:
        abort(404)

    base_dir = _recordings_dir()

    if os.path.isabs(ev.video_path):
        abs_path = os.path.abspath(ev.video_path)
    else:
        abs_path = os.path.abspath(os.path.join(base_dir, ev.video_path))

    if not abs_path.startswith(base_dir + os.sep):
        abort(403)

    if not os.path.isfile(abs_path):
        abort(404)

    audit(f"download_video:{event_id}", username=current_user.username)

    return send_file(abs_path, as_attachment=True, conditional=True)


def _recordings_dir() -> str:
    return os.path.abspath(os.path.join(current_app.root_path, "..", "recordings"))


@main_bp.get("/recordings")
@login_required
def recordings():
    base_dir = _recordings_dir()
    rows = []

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

    for root, _, files in os.walk(base_dir):
        for name in files:
            ext = os.path.splitext(name)[1].lower()

            if ext not in VIDEO_EXT:
                continue

            abs_path = os.path.abspath(os.path.join(root, name))

            if not abs_path.startswith(base_dir + os.sep):
                continue

            st = os.stat(abs_path)
            rel_path = os.path.relpath(abs_path, base_dir).replace("\\", "/")

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

    rows.sort(key=lambda r: r["dt"], reverse=True)

    audit(
        "view_recordings_folder",
        username=current_user.username,
        extra={"count": len(rows)},
    )

    return render_template("recordings.html", rows=rows, error=None)


@main_bp.get("/recordings/view/<path:rel_path>")
@login_required
def recordings_view(rel_path: str):
    base_dir = _recordings_dir()
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))

    if not abs_path.startswith(base_dir + os.sep):
        abort(403)

    if not os.path.isfile(abs_path):
        abort(404)

    ext = os.path.splitext(abs_path)[1].lower()
    guessed_mime = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"

    inline = ext in INLINE_VIDEO_EXT

    audit(
        "view_recording_file",
        username=current_user.username,
        extra={"file": rel_path},
    )

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
    base_dir = _recordings_dir()
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))

    if not abs_path.startswith(base_dir + os.sep):
        abort(403)

    if not os.path.isfile(abs_path):
        abort(404)

    audit(
        "download_recording_file",
        username=current_user.username,
        extra={"file": rel_path},
    )

    return send_file(abs_path, as_attachment=True, conditional=True)


def _mjpeg_stream(rtsp_url: str):
    transport = current_app.config.get("RTSP_TRANSPORT", "tcp").lower()
    jpeg_quality = int(current_app.config.get("MJPEG_QUALITY", 80))

    options = []

    if transport == "tcp":
        options.append("rtsp_transport;tcp")

    if options:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "|".join(options)

    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]

    cap = None
    fail_count = 0
    max_fail_count = 30

    try:
        while True:
            if cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not cap.isOpened():
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + _error_frame("Flux RTSP inaccessible")
                        + b"\r\n"
                    )

                    try:
                        cap.release()
                    except Exception:
                        pass

                    cap = None
                    time_module.sleep(2)
                    continue

                fail_count = 0

            ok, frame = cap.read()

            if not ok or frame is None:
                fail_count += 1
                time_module.sleep(0.2)

                if fail_count >= max_fail_count:
                    try:
                        cap.release()
                    except Exception:
                        pass

                    cap = None
                    fail_count = 0

                continue

            fail_count = 0
            frame = cv2.resize(frame, (960, 540))

            success, buffer = cv2.imencode(".jpg", frame, encode_params)

            if not success:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )

    finally:
        if cap is not None:
            cap.release()


def _error_frame(text_value: str) -> bytes:
    import numpy as np

    frame = np.zeros((480, 854, 3), dtype=np.uint8)

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

    ok, buffer = cv2.imencode(".jpg", frame)
    return buffer.tobytes() if ok else b""


@main_bp.post("/recordings/delete/<path:rel_path>")
@login_required
def recordings_delete(rel_path: str):
    try:
        base_dir = _recordings_dir()
        abs_path = os.path.abspath(os.path.join(base_dir, rel_path))

        if not abs_path.startswith(base_dir + os.sep):
            abort(403)

        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in VIDEO_EXT:
            abort(403)

        filename = os.path.basename(rel_path)

        if os.path.isfile(abs_path):
            os.remove(abs_path)

        linked_events = Event.query.filter(
            db.or_(
                Event.video_path == rel_path,
                Event.video_path == filename,
            )
        ).all()

        deleted_events = 0
        for event in linked_events:
            db.session.delete(event)
            deleted_events += 1

        db.session.commit()

        try:
            audit(
                "delete_recording_file",
                username=current_user.username,
                extra={
                    "file": rel_path,
                    "deleted_events": deleted_events,
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


@main_bp.post("/events/delete/<int:event_id>")
@login_required
def delete_event(event_id):
    try:
        event = Event.query.get_or_404(event_id)

        if event.video_path:
            base_dir = _recordings_dir()
            abs_path = os.path.abspath(os.path.join(base_dir, event.video_path))

            if abs_path.startswith(base_dir + os.sep) and os.path.exists(abs_path):
                os.remove(abs_path)

        db.session.delete(event)
        db.session.commit()

        try:
            audit("delete_event", username=current_user.username)
        except Exception as audit_error:
            current_app.logger.error(f"Erreur audit delete_event: {audit_error}")

        return redirect(url_for("main.events"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Erreur delete_event")
        return f"Erreur suppression : {e}", 500


@main_bp.route("/admin/alert-settings", methods=["GET", "POST"])
@login_required
def alert_settings():
    if getattr(current_user, "role", None) != "admin":
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))

    settings = AlertSettings.query.first()

    if not settings:
        settings = AlertSettings(
            enabled=True,
            start_time=dt_time(22, 0),
            end_time=dt_time(6, 0),
        )
        db.session.add(settings)
        db.session.commit()

    if request.method == "POST":
        settings.enabled = request.form.get("enabled") == "on"
        settings.start_time = dt_time.fromisoformat(request.form.get("start_time"))
        settings.end_time = dt_time.fromisoformat(request.form.get("end_time"))

        db.session.commit()

        flash("Paramètres d'alerte mis à jour", "success")
        return redirect(url_for("main.alert_settings"))

    return render_template("alert_settings.html", settings=settings)


@main_bp.route("/mindview")
def mindview():
    return render_template("mindview.html")


@main_bp.route("/mindview/download")
def download_mindview():
    file_path = "/home/enzo/eryma_web/app/static/downloads/PyVision_gantt.mvdx"

    if not os.path.isfile(file_path):
        return f"Fichier introuvable : {file_path}", 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name="PyVision_gantt.mvdx",
        mimetype="application/octet-stream",
    )


@main_bp.route("/admin/users")
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.id.asc()).all()
    return render_template("admin_users.html", users=users)


@main_bp.route("/admin/users/add", methods=["POST"])
@login_required
@admin_required
def admin_add_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    is_admin = request.form.get("is_admin") == "on"

    if not username or not password:
        flash("Le nom d'utilisateur et le mot de passe sont obligatoires", "error")
        return redirect(url_for("main.admin_users"))

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash("Cet utilisateur existe déjà", "error")
        return redirect(url_for("main.admin_users"))

    new_user = User(
        username=username,
        role="admin" if is_admin else "user",
        is_active=True,
    )

    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    flash("Utilisateur ajouté avec succès", "success")
    return redirect(url_for("main.admin_users"))


@main_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte", "error")
        return redirect(url_for("main.admin_users"))

    db.session.delete(user)
    db.session.commit()

    flash("Utilisateur supprimé avec succès", "success")
    return redirect(url_for("main.admin_users"))

@main_bp.route("/recordings/delete-all", methods=["POST"])
@login_required
def delete_all_recordings():
    recordings_dir = os.path.join(current_app.root_path, "static", "recordings")

    deleted_files = 0

    if os.path.exists(recordings_dir):
        for filename in os.listdir(recordings_dir):
            if filename.endswith((".mp4", ".mkv", ".webm", ".avi")):
                file_path = os.path.join(recordings_dir, filename)

                try:
                    os.remove(file_path)
                    deleted_files += 1
                except OSError:
                    pass

    # Supprime aussi les événements liés aux vidéos dans la BDD
    Event.query.filter(Event.video_filename.isnot(None)).delete()
    db.session.commit()

    flash(f"{deleted_files} enregistrement(s) s§upprimé(s)", "success")
    return redirect(url_for("main.recordings"))
