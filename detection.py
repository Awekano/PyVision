# detection.py
# Service de détection serveur PyVision
# Ce script lit le flux RTSP en continu, même si la page web n'est pas ouverte
# Il détecte les mouvements, enregistre une vidéo WebM et crée un événement en base de données

import os
import subprocess
import time
from datetime import datetime

import cv2
from sqlalchemy import text

from run import app
from app import db
from app.models import Event
from app.services.alert_settings import is_alert_allowed
from mailer import send_alert_email


# Durée de chaque vidéo enregistrée après détection
RECORD_SECONDS = 15

# Temps minimum entre deux enregistrements
# Valeur basse pour les tests
COOLDOWN_SECONDS = 15

# Sensibilité ultra forte pour les tests
MIN_MOTION_AREA = 5000
MOTION_FRAMES_REQUIRED = 15

# Paramètres vidéo
FRAME_WIDTH = 960
FRAME_HEIGHT = 540
FPS = 25


def get_recordings_dir():
    """Retourne le dossier des enregistrements et le crée si besoin."""
    recordings_dir = app.config.get("RECORDINGS_DIR")

    if not recordings_dir:
        recordings_dir = os.path.abspath(os.path.join(app.root_path, "..", "recordings"))

    os.makedirs(recordings_dir, exist_ok=True)
    return recordings_dir


def open_camera():
    """Ouvre le flux RTSP de la caméra IP."""
    rtsp_url = app.config.get("RTSP_URL")

    if not rtsp_url:
        raise RuntimeError("RTSP_URL non configurée")

    transport = app.config.get("RTSP_TRANSPORT", "tcp").lower()

    if transport == "tcp":
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    return cap


def create_detection_event(filename, is_alert):
    """Crée un événement dans la base de données."""
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

    try:
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
    except Exception as sql_error:
        print(f"[BDD] Colonnes supplémentaires non mises à jour : {sql_error}")

    db.session.commit()
    return event


def record_video(cap, first_frame=None):
    """Enregistre une vidéo WebM avec FFmpeg."""
    recordings_dir = get_recordings_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"motion_ip_server_{timestamp}.webm"
    filepath = os.path.join(recordings_dir, filename)

    command = [
        "ffmpeg",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{FRAME_WIDTH}x{FRAME_HEIGHT}",
        "-r", str(FPS),
        "-i", "-",
        "-an",
        "-c:v", "libvpx",
        "-b:v", "1M",
        "-deadline", "realtime",
        "-cpu-used", "5",
        filepath,
    ]

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    start_time = time.time()

    try:
        if first_frame is not None:
            frame = cv2.resize(first_frame, (FRAME_WIDTH, FRAME_HEIGHT))
            process.stdin.write(frame.tobytes())

        while time.time() - start_time < RECORD_SECONDS:
            ok, frame = cap.read()

            if not ok or frame is None:
                time.sleep(0.1)
                continue

            frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            process.stdin.write(frame.tobytes())

            time.sleep(1 / FPS)

    finally:
        try:
            if process.stdin:
                process.stdin.close()
        except Exception:
            pass

        process.wait()

    if not os.path.isfile(filepath) or os.path.getsize(filepath) < 1000:
        raise RuntimeError("Fichier WebM non créé ou invalide")

    return filename


def main():
    """Boucle principale de détection serveur."""
    with app.app_context():
        print("[PyVision] Service de détection serveur démarré")
        print("[PyVision] Mode test : WebM, sensibilité ultra forte")

        cap = None

        subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=50,
            detectShadows=True,
        )

        motion_counter = 0
        last_record_time = 0

        while True:
            try:
                if cap is None or not cap.isOpened():
                    print("[Caméra] Connexion au flux RTSP...")
                    cap = open_camera()

                    if not cap.isOpened():
                        print("[Caméra] Flux inaccessible, nouvelle tentative dans 5 secondes")
                        time.sleep(5)
                        continue

                    print("[Caméra] Flux RTSP connecté")

                ok, frame = cap.read()

                if not ok or frame is None:
                    print("[Caméra] Image non reçue, reconnexion...")
                    try:
                        cap.release()
                    except Exception:
                        pass

                    cap = None
                    time.sleep(2)
                    continue

                frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                mask = subtractor.apply(gray)
                mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)[1]
                mask = cv2.dilate(mask, None, iterations=2)

                contours, _ = cv2.findContours(
                    mask,
                    cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE,
                )

                motion_detected = False

                for contour in contours:
                    area = cv2.contourArea(contour)

                    if area >= MIN_MOTION_AREA:
                        motion_detected = True
                        break

                if motion_detected:
                    motion_counter += 1
                else:
                    motion_counter = 0

                now = time.time()

                if (
                    motion_counter >= MOTION_FRAMES_REQUIRED
                    and now - last_record_time >= COOLDOWN_SECONDS
                ):
                    print("[Détection] Mouvement détecté, enregistrement WebM lancé")

                    filename = record_video(cap, first_frame=frame)
                    is_alert = is_alert_allowed()

                    event = create_detection_event(filename, is_alert)

                    print(f"[BDD] Événement créé ID={event.id}, fichier={filename}")

                    if is_alert:
                        try:
                            mail_result = send_alert_email(filename, "alerte")

                            if mail_result is False:
                                print("[Mail] Alerte non envoyée")
                            else:
                                print("[Mail] Alerte envoyée")

                        except Exception as mail_error:
                            print(f"[Mail] Erreur envoi alerte : {mail_error}")
                    else:
                        print("[Mail] Non envoyé, hors plage d'alerte ou alerte désactivée")

                    last_record_time = time.time()
                    motion_counter = 0

                time.sleep(0.03)

            except Exception as error:
                print(f"[Erreur] {error}")

                try:
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass

                cap = None
                db.session.rollback()
                time.sleep(5)


if __name__ == "__main__":
    main()
