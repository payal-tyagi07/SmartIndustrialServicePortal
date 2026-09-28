from flask import request

from app.extensions import db
from app.models import AuditLog


def log_event(user_id, action, entity, entity_id, old_value=None, new_value=None):
    """Add an audit row to the current transaction; callers commit normally."""
    db.session.add(AuditLog(
        user_id=user_id, action=action, entity=entity, entity_id=entity_id,
        old_value=old_value, new_value=new_value,
        ip=request.headers.get("X-Forwarded-For", request.remote_addr or "")[:45],
    ))
