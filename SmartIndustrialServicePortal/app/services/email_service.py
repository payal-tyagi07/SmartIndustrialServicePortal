from flask import current_app, url_for
from flask_mail import Message

from app.extensions import mail


def send_password_reset_email(user, token):
    """Send a reset link; SMTP credentials always stay in environment variables."""
    link = url_for("auth.reset_password", token=token, _external=True)
    message = Message(
        subject="Reset your Smart Industrial Portal password",
        recipients=[user.email],
        body=("A password reset was requested for your account.\n\n"
              f"Reset your password: {link}\n\n"
              "This link expires in 30 minutes. If you did not request it, ignore this email."),
    )
    mail.send(message)


def send_technician_assignment_email(technician, complaint, reassigned=False):
    """Notify a non-authenticated technician of work allocated by an admin.

    Email delivery is deliberately best-effort: the assignment has already been
    committed and an SMTP outage must not lose the admin's operational update.
    """
    action = "reassigned" if reassigned else "assigned"
    message = Message(
        subject=f"Service request #{complaint.id} {action} to you",
        recipients=[technician.email],
        body=(f"Hello {technician.full_name},\n\n"
              f"You have been {action} service request #{complaint.id}.\n"
              f"Title: {complaint.title}\n"
              f"Location: {complaint.location}\n"
              f"Priority: {complaint.priority}\n"
              f"Description: {complaint.description}\n\n"
              "Please contact the service desk if you need more information."),
    )
    try:
        mail.send(message)
        return True
    except Exception:  # SMTP is an integration concern, not a transaction failure.
        current_app.logger.exception("Could not send assignment email for complaint %s", complaint.id)
        return False


