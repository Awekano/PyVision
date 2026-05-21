from sqlalchemy import text

from app import db
from app.models import Event
from app.services.alert_settings import is_alert_allowed
from mailer import send_alert_email


def create_event(kind: str = "video_recorded", video_path: str | None = None, screenshot_path: str | None = None):
    is_alert = is_alert_allowed()
    event_kind = "alerte" if is_alert else "video_recorded"

    event = Event(
        kind=event_kind,
        video_path=video_path,
        screenshot_path=screenshot_path,
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
            "description": "Alerte mail envoyée" if is_alert else "Vidéo enregistrée",
            "video_filename": video_path,
            "image_filename": screenshot_path,
            "kind": event_kind,
            "screenshot_path": screenshot_path,
            "video_path": video_path,
            "event_id": event.id,
        },
    )

    db.session.commit()

    if is_alert:
        try:
            send_alert_email(video_path, "alerte")
        except Exception as e:
            print(f"Erreur envoi mail : {e}")

    return event
