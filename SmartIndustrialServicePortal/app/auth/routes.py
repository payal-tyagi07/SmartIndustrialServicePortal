from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import select

from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def employee_login():
    if request.method == "POST":
        user = db.session.scalar(select(User).where(User.email == request.form["email"], User.role == "employee"))
        if user and user.is_active and user.check_password(request.form["password"]):
            session.clear(); session.update(role="employee", user_id=user.id)
            return redirect(url_for("employee.dashboard"))
        flash("Invalid employee credentials.", "danger")
    return render_template("login.html")


@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = db.session.scalar(select(User).where(User.username == request.form["username"], User.role == "admin"))
        if user and user.is_active and user.check_password(request.form["password"]):
            session.clear(); session.update(role="admin", user_id=user.id)
            return redirect(url_for("admin.dashboard"))
        flash("Invalid administrator credentials.", "danger")
    return render_template("admin_login.html")


@auth_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.employee_login"))
