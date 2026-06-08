import os
import smtplib
from email.message import EmailMessage

from app.models import AppSetting


def get_alert_email_recipient():
    setting = AppSetting.query.filter_by(setting_key="alert_email_recipient").first()

    if setting and setting.setting_value:
        return setting.setting_value

    return os.getenv("ALERT_EMAIL_TO")


def send_alert_email(video_filename, event_type="video_recorded"):
    recipient = get_alert_email_recipient()

    if not recipient:
        print("[Mail] Aucun destinataire mail configuré")
        return False

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM") or smtp_user

    missing = []

    if not smtp_host:
        missing.append("SMTP_HOST")

    if not smtp_user:
        missing.append("SMTP_USER")

    if not smtp_password:
        missing.append("SMTP_PASSWORD")

    if not smtp_from:
        missing.append("SMTP_FROM")

    if missing:
        print(f"[Mail] Configuration SMTP incomplète : {', '.join(missing)}")
        return False

    msg = EmailMessage()
    msg["Subject"] = "Alerte PyVision - Détection"
    msg["From"] = smtp_from
    msg["To"] = recipient

    msg.set_content(
        f"Une détection a eu lieu.\n\n"
        f"Type : {event_type}\n"
        f"Vidéo : {video_filename}"
    )

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)

        print(f"[Mail] Mail d'alerte envoyé à {recipient}")
        return True

    except Exception as e:
        print(f"[Mail] Erreur lors de l'envoi du mail : {e}")
        return False
