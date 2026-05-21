import os
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import Event

VIDEO_FOLDER = "/home/enzo/eryma_web/recordings"

def cleanup_old_videos():
    limit_date = datetime.utcnow() - timedelta(days=30)

    old_events = Event.query.filter(Event.created_at < limit_date).all()

    for event in old_events:
        video_path = event.video_path

        if video_path:
            # sécuriser le chemin
            full_path = video_path
            if not video_path.startswith("/"):
                full_path = os.path.join(VIDEO_FOLDER, video_path)

            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    print(f"[OK] Supprimé : {full_path}")
                except Exception as e:
                    print(f"[ERREUR] suppression fichier : {e}")

        db.session.delete(event)

    db.session.commit()
    print(f"[OK] Nettoyage terminé ({len(old_events)} éléments)")
