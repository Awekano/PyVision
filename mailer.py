# mailer.py
import os
import smtplib
import ssl
from email.message import EmailMessage


def send_alert_email(video_filename, event_type="video_recorded"):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    mail_from = os.getenv("MAIL_FROM", smtp_user)
    mail_to = os.getenv("ALERT_EMAIL")

    if not all([smtp_host, smtp_user, smtp_password, mail_to]):
        print("Config SMTP incomplète")
        return

    msg = EmailMessage()
    msg["Subject"] = "[ERYMA] Nouvelle vidéo enregistrée"
    msg["From"] = mail_from
    msg["To"] = mail_to

    msg.set_content(
        f"""Bonjour,

Une nouvelle vidéo a été enregistrée.

Type d'évènement : {event_type}
Nom du fichier : {video_filename}

Connecte-toi à pyvision.enzofile.fr  pour la consulter.

Message automatique.
"""
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)
