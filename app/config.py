import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Exemple : rtsp://user:motdepasse@192.168.10.20:554/Streaming/Channels/101
    RTSP_URL = os.getenv("RTSP_URL")
    RTSP_TRANSPORT = os.getenv("RTSP_TRANSPORT", "tcp")
    MJPEG_QUALITY = int(os.getenv("MJPEG_QUALITY", "80"))
