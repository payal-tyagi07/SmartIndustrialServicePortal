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
