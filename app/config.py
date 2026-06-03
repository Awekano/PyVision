# app/config.py
# Ce fichier contient la configuration principale de l'application

import os


class Config:
    # Clé secrète utilisée par Flask pour les sessions
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    # Adresse de connexion à la base de données
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    # Désactive le suivi inutile des modifications SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Exemple de flux caméra :
    # rtsp://user:motdepasse@192.168.10.20:554/Streaming/Channels/101

    # URL du flux RTSP de la caméra IP
    RTSP_URL = os.getenv("RTSP_URL")

    # Transport utilisé pour le flux RTSP
    RTSP_TRANSPORT = os.getenv("RTSP_TRANSPORT", "tcp")

    # Qualité JPEG du flux MJPEG envoyé au navigateur
    MJPEG_QUALITY = int(os.getenv("MJPEG_QUALITY", "80"))
