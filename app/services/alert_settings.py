from datetime import datetime
from app import db
from app.models import AlertSettings

def is_alert_allowed():
    settings = AlertSettings.query.first()

    if not settings or not settings.enabled:
        return False

    now = datetime.now().time()
    start = settings.start_time
    end = settings.end_time

    # Cas normal : 08:00 -> 18:00
    if start < end:
        return start <= now <= end

    # Cas nuit : 22:00 -> 06:00
    return now >= start or now <= end
