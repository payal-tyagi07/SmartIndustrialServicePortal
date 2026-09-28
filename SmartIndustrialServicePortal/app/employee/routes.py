from flask import Blueprint, render_template, session
from sqlalchemy import select

from app.extensions import db
from app.models import Complaint
from app.decorators import employee_required

employee_bp = Blueprint("employee", __name__)


@employee_bp.get("/dashboard")
@employee_required
def dashboard():
    tickets = db.session.scalars(select(Complaint).where(Complaint.employee_id == session.get("user_id")).order_by(Complaint.created_at.desc()).limit(5)).all()
    return render_template("employee_dashboard.html", recent_complaints=tickets, stats={})
