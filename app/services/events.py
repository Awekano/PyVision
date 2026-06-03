# app/services/events.py
# Ce fichier sert à créer un événement caméra dans la base
# Il peut aussi envoyer un mail si l'alerte est autorisée

from sqlalchemy import text

from app import db
from app.models import Event
from app.services.alert_settings import is_alert_allowed
from mailer import send_alert_email


def create_event(kind: str = "video_recorded", video_path: str | None = None, screenshot_path: str | None = None):
    # Vérifie si l'événement doit être considéré comme une alerte
    is_alert = is_alert_allowed()

    # Si l'alerte est autorisée, l'événement devient une alerte
    event_kind = "alerte" if is_alert else "video_recorded"

    # Création de l'événement avec les colonnes déclarées dans le modèle SQLAlchemy
    event = Event(
        kind=event_kind,
        video_path=video_path,
        screenshot_path=screenshot_path,
    )

    # Ajout temporaire de l'événement dans la session
    db.session.add(event)

    # Flush pour récupérer l'ID avant le commit final
    db.session.flush()

    # Mise à jour des colonnes supplémentaires existantes dans MariaDB
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

    # Validation en base de données
    db.session.commit()

    # Envoi du mail uniquement si l'alerte est autorisée
    if is_alert:
        try:
            send_alert_email(video_path, "alerte")
        except Exception as e:
            print(f"Erreur envoi mail : {e}")

    # Retourne l'événement créé
    return event
