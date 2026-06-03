# mailer.py
# Ce fichier gère l'envoi des mails d'alerte du projet PyVision

import os
import smtplib
import ssl
from email.message import EmailMessage


def send_alert_email(video_filename, event_type="video_recorded"):
    # Récupération des paramètres SMTP depuis le fichier .env
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    mail_from = os.getenv("MAIL_FROM", smtp_user)
    mail_to = os.getenv("ALERT_EMAIL")

    # Vérification que la configuration SMTP est complète
    if not all([smtp_host, smtp_user, smtp_password, mail_to]):
        print("Config SMTP incomplète")
        return

    # Création du message mail
    msg = EmailMessage()
    msg["Subject"] = "[ERYMA] Nouvelle vidéo enregistrée"
    msg["From"] = mail_from
    msg["To"] = mail_to

    # Contenu du mail envoyé au client
    msg.set_content(
        f"""Bonjour,

Une nouvelle vidéo a été enregistrée.

Type d'évènement : {event_type}
Nom du fichier : {video_filename}

Connecte-toi à pyvision.enzofile.fr pour la consulter.

Message automatique.
"""
    )

    # Création d'une connexion sécurisée SSL
    context = ssl.create_default_context()

    # Connexion au serveur SMTP et envoi du message
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)
