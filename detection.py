# detection.py
# Ce fichier sert de test simple pour créer un événement de détection vidéo

from mailer import send_alert_email
from app.services.events import create_event
from app.services.alert_settings import is_alert_allowed

# Nom d'une vidéo de démonstration
video_name = "motion_demo_admin_20260329_164103.webm"

# Création d'un événement de détection dans la base
create_event(
    kind="motion",
    video_path=video_name
)
