# app/services/audit.py
# Ce fichier ajoute une ligne dans le journal de bord à chaque action importante

from flask import request
from .. import db
from ..models import AuditLog


def audit(action: str, username: str | None = None, extra: dict | None = None) -> None:
    # Création d'une nouvelle entrée dans le journal de bord
    entry = AuditLog(
        username=username,
        action=action,
        ip=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=request.headers.get("User-Agent", "")[:250],
    )

    # Ajout dans la base de données
    db.session.add(entry)

    # Validation de l'ajout
    db.session.commit()
