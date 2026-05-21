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
from app.models import AlertSettings, AuditLog, Event
from app.services.alert_settings import is_alert_allowed
from app.services.audit import audit
from mailer import send_alert_email

main_bp = Blueprint("main", __name__)

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
INLINE_VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov"}
UPLOAD_EXT = {".webm", ".mp4", ".mkv"}


@main_bp.get("/")
@login_required
def index():
    return render_template("index.html")


@main_bp.get("/events")
@login_required
def events():
    kind = request.args.get("kind")
    q = Event.query.order_by(Event.created_at.desc())

    if kind in ("detection", "alarme", "alerte", "alert", "video_recorded"):
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

    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + _error_frame("Flux RTSP inaccessible")
            + b"\r\n"
        )
        return

    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                time_module.sleep(0.2)
                continue

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


@main_bp.post("/upload_webcam_recording")
@login_required
def upload_webcam_recording():
    try:
        file = request.files.get("video")

        if not file:
            return jsonify({"error": "Aucun fichier reçu"}), 400

        original_name = secure_filename(file.filename or "")
        ext = Path(original_name).suffix.lower()

        if ext not in UPLOAD_EXT:
            return jsonify({"error": f"Extension non autorisée : {ext}"}), 400

        recordings_dir = _recordings_dir()
        os.makedirs(recordings_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"motion_demo_{current_user.username}_{timestamp}{ext}"
        save_path = os.path.join(recordings_dir, filename)

        file.save(save_path)

        rel_path = filename
        is_alert = is_alert_allowed()
        event_kind = "alerte" if is_alert else "video_recorded"
        description = "Alerte mail envoyée" if is_alert else "Vidéo enregistrée"

        # Le modèle Event de ton projet ne déclare pas toutes les colonnes SQL
        # présentes dans MariaDB. On crée donc l'évènement avec les colonnes du
        # modèle, puis on met à jour les colonnes SQL supplémentaires en requête brute.
        event = Event(
            kind=event_kind,
            video_path=rel_path,
            screenshot_path=None,
        )

        db.session.add(event)
        db.session.flush()

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

        db.session.commit()

        if is_alert:
            try:
                send_alert_email(rel_path, "alerte")
            except Exception as e:
                current_app.logger.error(f"Erreur envoi mail : {e}")
        else:
            current_app.logger.info(
                "Alerte mail non envoyée : hors plage horaire ou désactivée"
            )

        try:
            audit(
                "upload_webcam_recording",
                username=current_user.username,
                extra={"file": filename, "event_id": event.id, "kind": event_kind},
            )
        except Exception as audit_error:
            current_app.logger.error(f"Erreur audit upload_webcam_recording: {audit_error}")

        return jsonify(
            {
                "message": "Vidéo enregistrée",
                "filename": filename,
                "event_id": event.id,
                "type": event_kind,
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Erreur upload_webcam_recording")
        return jsonify({"error": str(e)}), 500


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
        mimetype="application/octet-stream"
    )
