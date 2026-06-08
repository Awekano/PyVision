import os
import time
from datetime import datetime
from pathlib import Path

import cv2
from sqlalchemy import text

from app import create_app, db
from app.models import Event
from app.services.alert_settings import is_alert_allowed
from app.services.camera_mode import get_camera_recording_mode, MODE_SERVER
from mailer import send_alert_email


RECORD_SECONDS = 10
COOLDOWN_SECONDS = 5
MOTION_THRESHOLD = 28
MOTION_PIXELS_MIN = 1800


app = create_app()


def recordings_dir():
    base_dir = Path(__file__).resolve().parent / "recordings"
    base_dir.mkdir(exist_ok=True)
    return base_dir


def create_event_and_send_mail(filename):
    is_alert = is_alert_allowed()
    event_kind = "alerte" if is_alert else "video_recorded"

    description = (
        "Détection caméra IP avec alerte mail"
        if is_alert
        else "Détection caméra IP hors plage d'alerte"
    )

    event = Event(
        kind=event_kind,
        video_path=filename,
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
            "camera_name": "Camera IP",
            "description": description,
            "video_filename": filename,
            "image_filename": None,
            "kind": event_kind,
            "screenshot_path": None,
            "video_path": filename,
            "event_id": event.id,
        },
    )

    db.session.commit()

    if is_alert:
        send_alert_email(filename, "alerte")

    print(f"Événement créé : {event_kind} / {filename}")


def record_video(cap, save_path, width, height, fps=20):
    fourcc = cv2.VideoWriter_fourcc(*"VP80")
    writer = cv2.VideoWriter(str(save_path), fourcc, fps, (width, height))
    
    if not writer.isOpened():
        raise RuntimeError("Impossible de créer la vidéo webm avec OpenCV")

    end_time = time.time() + RECORD_SECONDS

    while time.time() < end_time:
        ok, frame = cap.read()

        if not ok or frame is None:
            time.sleep(0.1)
            continue

        frame = cv2.resize(frame, (width, height))
        writer.write(frame)

    writer.release()


def main():
    rtsp_url = app.config.get("RTSP_URL")

    if not rtsp_url:
        raise RuntimeError("RTSP_URL non configurée dans .env")

    transport = app.config.get("RTSP_TRANSPORT", "tcp").lower()

    if transport == "tcp":
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

    with app.app_context():
        previous_gray = None
        last_record_time = 0

        while True:
            mode = get_camera_recording_mode()

            if mode != MODE_SERVER:
                print("Mode live uniquement : worker serveur en pause")
                previous_gray = None
                time.sleep(5)
                continue

            print("Connexion au flux caméra...")
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                print("Flux RTSP inaccessible, nouvelle tentative dans 5 secondes")
                time.sleep(5)
                continue

            print("Surveillance caméra active")

            while True:
                mode = get_camera_recording_mode()

                if mode != MODE_SERVER:
                    print("Mode live uniquement : worker serveur en pause")
                    previous_gray = None
                    cap.release()
                    time.sleep(5)
                    break

                ok, frame = cap.read()

                if not ok or frame is None:
                    print("Image caméra illisible, reconnexion...")
                    previous_gray = None
                    cap.release()
                    time.sleep(2)
                    break

                frame = cv2.resize(frame, (960, 540))
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                if previous_gray is None:
                    previous_gray = gray
                    continue

                diff = cv2.absdiff(previous_gray, gray)
                _, thresh = cv2.threshold(diff, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)
                changed_pixels = cv2.countNonZero(thresh)

                previous_gray = gray

                if changed_pixels > MOTION_PIXELS_MIN:
                    now = time.time()

                    if now - last_record_time < COOLDOWN_SECONDS:
                        continue

                    last_record_time = now

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"motion_ip_server_{timestamp}.webm"
                    save_path = recordings_dir() / filename

                    print(f"Mouvement détecté, enregistrement : {filename}")

                    record_video(cap, save_path, 960, 540)

                    create_event_and_send_mail(filename)

                time.sleep(0.05)


if __name__ == "__main__":
    main()
