"""The single server-side source of truth for complaint workflow and SLA rules."""
from datetime import datetime, timedelta

from app.extensions import db
from app.models import StatusHistory

SLA_MINUTES = {"Critical": 30, "High": 120, "Medium": 480, "Low": 1440}
TERMINAL_STATUSES = {"Resolved", "Rejected"}
ALLOWED_TRANSITIONS = {
    "Pending": {"Assigned", "Rejected"},
    "Assigned": {"Pending", "In Progress", "Rejected"},
    "In Progress": {"Assigned", "Resolved", "Rejected"},
    "Resolved": set(),
    "Rejected": set(),
}


def sla_deadline(priority, now=None):
    """Return the UTC deadline for a newly submitted complaint."""
    return (now or datetime.utcnow()) + timedelta(minutes=SLA_MINUTES[priority])


def can_transition(old_status, new_status):
    return new_status in ALLOWED_TRANSITIONS.get(old_status, set())


def transition_complaint(complaint, new_status, changed_by_id, note=None):
    """Validate and persist a status change, including its immutable history row."""
    if not can_transition(complaint.status, new_status):
        raise ValueError(f"{complaint.status} cannot transition to {new_status}.")
    old_status = complaint.status
    complaint.status = new_status
    db.session.add(StatusHistory(
        complaint=complaint,
        changed_by_id=changed_by_id,
        old_status=old_status,
        new_status=new_status,
        note=note,
    ))
    return complaint


def countdown_text(due_at, now=None):
    if not due_at:
        return "SLA not started"
    seconds = int((due_at - (now or datetime.utcnow())).total_seconds())
    prefix = "Breached by " if seconds < 0 else "Due in "
    minutes = abs(seconds) // 60
    return f"{prefix}{minutes // 60}h {minutes % 60:02d}m"
