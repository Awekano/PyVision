import cv2
import os
import time
from datetime import datetime
from threading import Lock

from app import db
from app.models import Event
from mailer import send_alert_email

camera_lock = Lock()

CAMERA_URL = os.getenv("CAMERA_URL")
RECORDINGS_DIR = os.getenv("RECORDINGS_DIR", "recordings")
MOTION_MIN_AREA = int(os.getenv("MOTION_MIN_AREA", 2500))
RECORD_SECONDS = int(os.getenv("RECORD_SECONDS", 15))

os.makedirs(RECORDINGS_DIR, exist_ok=True)

last_record_time = 0
COOLDOWN_SECONDS = 20


def save_event(video_filename):
    event = Event(
        event_type="detection",
        kind="alerte",
        camera_name="Camera IP",
        description="Mouvement détecté sur la caméra IP",
        video_filename=video_filename,
        video_path=video_filename,
        created_at=datetime.now()
    )

    db.session.add(event)
    db.session.commit()


def record_video(frame, cap):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"detection_{timestamp}.mkv"
    filepath = os.path.join(RECORDINGS_DIR, filename)

    height, width = frame.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"X264")
    out = cv2.VideoWriter(filepath, fourcc, 20.0, (width, height))

    start = time.time()

    while time.time() - start < RECORD_SECONDS:
        ret, frame = cap.read()
        if not ret:
            break

        out.write(frame)

    out.release()

    save_event(filename)

    try:
        send_alert_email(filename, "alerte")
    except Exception as e:
        print("Erreur mail :", e)

    return filename


def generate_camera_stream(app):
    global last_record_time

    cap = cv2.VideoCapture(CAMERA_URL)

    if not cap.isOpened():
        print("Impossible d'ouvrir le flux caméra")
        return

    first_frame = None

    while True:
        ret, frame = cap.read()

        if not ret:
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(CAMERA_URL)
            continue

        frame = cv2.resize(frame, (960, 540))

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if first_frame is None:
            first_frame = gray
            continue

        frame_delta = cv2.absdiff(first_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(
            thresh.copy(),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        motion_detected = False

        for contour in contours:
            if cv2.contourArea(contour) < MOTION_MIN_AREA:
                continue

            motion_detected = True

            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                frame,
                "Mouvement detecte",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

        if motion_detected and time.time() - last_record_time > COOLDOWN_SECONDS:
            last_record_time = time.time()

            with app.app_context():
                record_video(frame, cap)

        ret, buffer = cv2.imencode(".jpg", frame)

        if not ret:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            buffer.tobytes() +
            b"\r\n"
        )
