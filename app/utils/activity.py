from flask import request

from app.extensions import db
from app.models import ActivityLog


def log_activity(user_id, action: str, details: str = None) -> None:
    entry = ActivityLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=request.remote_addr if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
    )
    db.session.add(entry)
    db.session.commit()
