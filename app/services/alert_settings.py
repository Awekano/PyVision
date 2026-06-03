# app/services/alert_settings.py
# Ce fichier vérifie si l'envoi d'une alerte mail est autorisé
# selon les horaires configurés par l'administrateur

from datetime import datetime
from app.models import AlertSettings


def is_alert_allowed():
    # Récupération des paramètres d'alerte dans la base
    settings = AlertSettings.query.first()

    # Si aucun paramètre n'existe ou si les alertes sont désactivées
    if not settings or not settings.enabled:
        return False

    # Heure actuelle
    now = datetime.now().time()

    # Heure de début et heure de fin configurées
    start = settings.start_time
    end = settings.end_time

    # Cas normal : exemple 08:00 -> 18:00
    if start < end:
        return start <= now <= end

    # Cas d'une plage de nuit : exemple 22:00 -> 06:00
    return now >= start or now <= end
