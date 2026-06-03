# run.py
# Ce fichier sert à lancer l'application Flask PyVision

from app import create_app
import os

# Création de l'application Flask depuis la fonction create_app
app = create_app()

# Configuration du dossier où sont stockés les enregistrements vidéo
app.config["RECORDINGS_DIR"] = os.path.abspath(
    os.path.join(app.root_path, "..", "recordings")
)

# Lancement du serveur Flask si ce fichier est exécuté directement
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
