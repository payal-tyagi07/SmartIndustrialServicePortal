from app.extensions import db
from app.models import Notification


def notify(user_id: int, title: str, message: str) -> Notification:
    notification = Notification(user_id=user_id, title=title, message=message)
    db.session.add(notification)
    return notification
