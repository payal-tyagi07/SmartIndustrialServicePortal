from datetime import datetime, timedelta

import pyotp
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select

from app.extensions import db, limiter
from app.decorators import admin_required
from app.models import User
from app.services.email_service import send_password_reset_email

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/")
def home():
    if session.get("role") == "employee":
        return redirect(url_for("employee.dashboard"))
    if session.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))
    return render_template("index.html")


@auth_bp.get("/about")
def about():
    return render_template("about.html")


@auth_bp.get("/contact")
def contact():
    return render_template("contact.html")


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _reset_token(user):
    # Password-change timestamp invalidates every older reset link.
    return _serializer().dumps({"id": user.id, "changed": user.password_changed_at.isoformat()}, salt=current_app.config["RESET_TOKEN_SALT"])


def _user_from_reset_token(token):
    payload = _serializer().loads(token, salt=current_app.config["RESET_TOKEN_SALT"], max_age=current_app.config["RESET_TOKEN_MAX_AGE"])
    user = db.session.get(User, payload["id"])
    if not user or user.password_changed_at.isoformat() != payload["changed"]:
        raise BadSignature("Token is no longer valid")
    return user


def _login_user(user):
    session.clear()
    session.permanent = True
    session.update(role=user.role, user_id=user.id)
    if user.role == "employee":
        session.update(employee_id=user.id, employee_name=user.full_name, employee_dept=user.department)
    else:
        session.update(admin_id=user.id, admin_username=user.username)


def _authenticate(user, password, role):
    if not user or not user.is_active or user.role != role:
        return False, "Invalid credentials."
    if user.locked_until and user.locked_until > datetime.utcnow():
        return False, "This account is temporarily locked. Try again later."
    if not user.check_password(password):
        user.failed_login_count += 1
        if user.failed_login_count >= 5:
            user.failed_login_count = 0
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.session.commit()
        return False, "Invalid credentials."
    user.failed_login_count = 0
    user.locked_until = None
    db.session.commit()
    return True, ""


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def employee_login():
    if request.method == "POST":
        user = db.session.scalar(select(User).where(User.email == request.form["email"], User.role == "employee"))
        authenticated, error = _authenticate(user, request.form["password"], "employee")
        if authenticated:
            _login_user(user)
            return redirect(url_for("employee.dashboard"))
        flash(error, "danger")
    return render_template("login.html")


@auth_bp.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def admin_login():
    if request.method == "POST":
        user = db.session.scalar(select(User).where(User.username == request.form["username"], User.role == "admin"))
        authenticated, error = _authenticate(user, request.form["password"], "admin")
        if authenticated and user.totp_enabled:
            session.clear(); session["pending_2fa_admin_id"] = user.id
            return redirect(url_for("auth.verify_admin_2fa"))
        if authenticated:
            _login_user(user)
            return redirect(url_for("admin.dashboard"))
        flash(error, "danger")
    return render_template("admin_login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        if db.session.scalar(select(User.id).where(User.email == email)):
            flash("An account already exists for that email address.", "danger")
        elif len(request.form["password"]) < 12:
            flash("Use a password with at least 12 characters.", "danger")
        else:
            user = User(full_name=request.form["full_name"].strip(), email=email, department=request.form["department"].strip(), role="employee")
            user.set_password(request.form["password"])
            db.session.add(user); db.session.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("auth.employee_login"))
    return render_template("register.html")


@auth_bp.route("/password-reset", methods=["GET", "POST"])
@limiter.limit("3 per hour")
def request_password_reset():
    if request.method == "POST":
        user = db.session.scalar(select(User).where(User.email == request.form["email"].strip().lower()))
        if user and user.is_active:
            send_password_reset_email(user, _reset_token(user))
        flash("If the account exists, a reset link has been sent.", "success")
        return redirect(url_for("auth.employee_login"))
    return render_template("password_reset_request.html")


@auth_bp.route("/password-reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        user = _user_from_reset_token(token)
    except (BadSignature, SignatureExpired):
        flash("This password-reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.request_password_reset"))
    if request.method == "POST":
        password = request.form["password"]
        if len(password) < 12 or password != request.form["confirm_password"]:
            flash("Passwords must match and contain at least 12 characters.", "danger")
        else:
            user.set_password(password); user.failed_login_count = 0; user.locked_until = None
            db.session.commit()
            flash("Password updated. Please log in.", "success")
            return redirect(url_for("auth.employee_login"))
    return render_template("password_reset_form.html", token=token)


@auth_bp.route("/admin/verify-2fa", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def verify_admin_2fa():
    user = db.session.get(User, session.get("pending_2fa_admin_id"))
    if not user or user.role != "admin" or not user.totp_enabled:
        return redirect(url_for("auth.admin_login"))
    if request.method == "POST" and pyotp.TOTP(user.totp_secret).verify(request.form["code"], valid_window=1):
        _login_user(user)
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        flash("Invalid verification code.", "danger")
    return render_template("admin_2fa.html")


@auth_bp.route("/admin/2fa/setup", methods=["GET", "POST"])
@admin_required
def setup_admin_2fa():
    """Optional admin-only TOTP enrollment; technicians never use this flow."""
    user = db.session.get(User, session["user_id"])
    if not user.totp_secret:
        user.totp_secret = pyotp.random_base32()
        db.session.commit()
    if request.method == "POST":
        if pyotp.TOTP(user.totp_secret).verify(request.form["code"], valid_window=1):
            user.totp_enabled = True
            db.session.commit()
            flash("Two-factor authentication is enabled.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Invalid verification code.", "danger")
    return render_template(
        "admin_2fa_setup.html",
        secret=user.totp_secret,
        provisioning_uri=pyotp.TOTP(user.totp_secret).provisioning_uri(name=user.email, issuer_name="Smart Industrial Portal"),
    )


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.employee_login"))
