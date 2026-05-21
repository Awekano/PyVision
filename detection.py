from mailer import send_alert_email
from app.services.events import create_event
from app.services.alert_settings import is_alert_allowed

video_name = "motion_demo_admin_20260329_164103.webm"

create_event(
    kind="motion",
    video_path=video_name
)


