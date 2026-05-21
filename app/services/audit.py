from flask import request
from .. import db
from ..models import AuditLog

def audit(action: str, username: str | None = None, extra: dict | None = None) -> None:
    entry = AuditLog(
        username=username,
        action=action,
        ip=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=request.headers.get("User-Agent", "")[:250],
    )
    db.session.add(entry)
    db.session.commit()
