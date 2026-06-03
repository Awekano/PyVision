# cleanup_old_recordings.py
# Supprime automatiquement les vidéos de plus de 30 jours

import os
from datetime import datetime, timedelta

from app import create_app, db
from app.models import Event


# Durée maximale de conservation des vidéos selon la règle définie pour le projet
RETENTION_DAYS = 30

# Dossier contenant les enregistrements vidéo
RECORDINGS_DIR = "/home/enzo/eryma_web/recordings"

# Extensions vidéo à nettoyer
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}


def cleanup_old_recordings():
    app = create_app()

    with app.app_context():
        limit_date = datetime.now() - timedelta(days=RETENTION_DAYS)

        deleted_files = 0
        deleted_events = 0

        # Suppression des fichiers vidéo trop anciens
        for root, _, files in os.walk(RECORDINGS_DIR):
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()

                if ext not in VIDEO_EXTENSIONS:
                    continue

                file_path = os.path.join(root, filename)
                file_modified_date = datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_modified_date < limit_date:
                    try:
                        os.remove(file_path)
                        deleted_files += 1
                        print(f"Vidéo supprimée : {file_path}")
                    except Exception as e:
                        print(f"Erreur suppression fichier {file_path} : {e}")

        # Suppression des événements vidéo trop anciens dans la BDD
        old_events = Event.query.filter(Event.created_at < limit_date).all()

        for event in old_events:
            db.session.delete(event)
            deleted_events += 1

        db.session.commit()

        print(f"Nettoyage terminé")
        print(f"Fichiers supprimés : {deleted_files}")
        print(f"Événements supprimés : {deleted_events}")


if __name__ == "__main__":
    cleanup_old_recordings()
