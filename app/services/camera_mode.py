from app import db
from app.models import AppSetting


CAMERA_MODE_KEY = "camera_recording_mode"

MODE_SERVER = "server"
MODE_LIVE = "live"


def get_camera_recording_mode():
    setting = AppSetting.query.filter_by(setting_key=CAMERA_MODE_KEY).first()

    if not setting or not setting.setting_value:
        return MODE_LIVE

    if setting.setting_value not in (MODE_SERVER, MODE_LIVE):
        return MODE_LIVE

    return setting.setting_value


def set_camera_recording_mode(mode):
    if mode not in (MODE_SERVER, MODE_LIVE):
        raise ValueError("Mode caméra invalide")

    setting = AppSetting.query.filter_by(setting_key=CAMERA_MODE_KEY).first()

    if not setting:
        setting = AppSetting(
            setting_key=CAMERA_MODE_KEY,
            setting_value=mode
        )
        db.session.add(setting)
    else:
        setting.setting_value = mode

    db.session.commit()
