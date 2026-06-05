import os
import smtplib
from email.message import EmailMessage

from app.models import AppSetting


def get_alert_email_recipient():
    # Cherche dans la BDD le mail destinataire des alertes
    setting = AppSetting.query.filter_by(setting_key="alert_email_recipient").first()

    # Si une adresse est trouvée en BDD, on l'utilise
    if setting and setting.setting_value:
        return setting.setting_value

    # Sinon on utilise l'adresse du fichier .env en secours
    return os.getenv("ALERT_EMAIL_TO")


def send_alert_email(video_filename, event_type="video_recorded"):
    # Récupère l'adresse mail du destinataire depuis la BDD
    recipient = get_alert_email_recipient()

    # Si aucun destinataire n'est configuré, on annule l'envoi du mail
    if not recipient:
        print("Aucun destinataire mail configuré")
        return

    # Récupère les informations SMTP depuis le fichier .env
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM")

    # Vérifie que la configuration SMTP est complète
    if not smtp_host or not smtp_user or not smtp_password or not smtp_from:
        print("Configuration SMTP incomplète")
        return

    # Création du message mail
    msg = EmailMessage()

    # Sujet du mail
    msg["Subject"] = "Alerte PyVision - Détection"

    # Adresse mail qui envoie l'alerte
    # Elle reste dans le fichier .env
    msg["From"] = smtp_from

    # Adresse mail qui reçoit l'alerte
    # Elle est récupérée depuis la BDD
    msg["To"] = recipient

    # Contenu du mail
    msg.set_content(
        f"Une détection a eu lieu.\n\n"
        f"Type : {event_type}\n"
        f"Vidéo : {video_filename}"
    )

    try:
        # Connexion au serveur SMTP en SSL
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            # Connexion au compte mail expéditeur
            smtp.login(smtp_user, smtp_password)

            # Envoi du mail au destinataire
            smtp.send_message(msg)

        print(f"Mail d'alerte envoyé à {recipient}")

    except Exception as e:
        # Affiche l'erreur si l'envoi du mail échoue
        print(f"Erreur lors de l'envoi du mail : {e}")
