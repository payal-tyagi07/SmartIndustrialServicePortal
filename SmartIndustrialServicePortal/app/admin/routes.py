from flask import Blueprint, render_template
from sqlalchemy import select

from app.extensions import db
from app.models import Complaint, Technician
from app.decorators import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    return render_template("admin_dashboard.html", complaints=db.session.scalars(select(Complaint)).all())


@admin_bp.get("/technicians")
@admin_required
def technicians():
    return render_template("admin_technicians.html", technicians=db.session.scalars(select(Technician).order_by(Technician.full_name)).all())
