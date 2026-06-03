# cleanup.py
# Ce fichier sert à supprimer les anciennes vidéos et les anciens événements
# Il permet de garder seulement les données récentes du projet

import os
from datetime import datetime, timedelta

from app import create_app, db
from app.models import Event

# Dossier où sont stockées les vidéos enregistrées
VIDEO_FOLDER = "/home/enzo/eryma_web/recordings"


def cleanup_old_videos():
    # Date limite : tous les événements plus vieux que 30 jours seront supprimés
    limit_date = datetime.utcnow() - timedelta(days=30)

    # Récupération des anciens événements dans la base
    old_events = Event.query.filter(Event.created_at < limit_date).all()

    # Parcours des anciens événements
    for event in old_events:
        video_path = event.video_path

        # Si l'événement possède une vidéo associée
        if video_path:
            # Création du chemin complet vers la vidéo
            full_path = video_path

            # Si le chemin n'est pas absolu, on l'ajoute au dossier recordings
            if not video_path.startswith("/"):
                full_path = os.path.join(VIDEO_FOLDER, video_path)

            # Suppression du fichier vidéo s'il existe
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    print(f"[OK] Supprimé : {full_path}")
                except Exception as e:
                    print(f"[ERREUR] suppression fichier : {e}")

        # Suppression de l'événement dans la base
        db.session.delete(event)

    # Validation des suppressions dans la base
    db.session.commit()
    print(f"[OK] Nettoyage terminé ({len(old_events)} éléments)")


# Lancement du nettoyage si le fichier est exécuté directement
if __name__ == "__main__":
    app = create_app()

    # On lance le nettoyage dans le contexte Flask
    with app.app_context():
        cleanup_old_videos()
