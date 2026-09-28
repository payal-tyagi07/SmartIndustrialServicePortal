from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.decorators import admin_required
from app.extensions import db
from app.models import Assignment, AssignmentHistory, AuditLog, Complaint, StatusHistory, Technician
from app.services.email_service import send_technician_assignment_email
from app.services.workflow_service import can_transition, transition_complaint
from app.services.audit_service import log_event

admin_bp = Blueprint("admin", __name__)
ACTIVE_STATUSES = ("Assigned", "In Progress")
VALID_STATUSES = ("Pending", "Assigned", "In Progress", "Resolved", "Rejected")
AVAILABILITY = ("Available", "Busy", "Unavailable")


def _technician_form():
    return {field: request.form.get(field, "").strip() for field in ("full_name", "email", "phone", "department", "skills", "availability")}


def _valid_technician(data, existing_id=None):
    if not all(data[field] for field in ("full_name", "email", "phone", "department", "skills")):
        return "Name, email, phone, department, and skills are required."
    if "@" not in data["email"] or data["availability"] not in AVAILABILITY:
        return "Enter a valid email address and availability."
    duplicate = db.session.scalar(select(Technician.id).where(func.lower(Technician.email) == data["email"].lower()))
    if duplicate and duplicate != existing_id:
        return "A technician already uses that email address."


@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    return render_template("admin_dashboard.html", complaints=db.session.scalars(select(Complaint)).all())


@admin_bp.get("/complaints")
@admin_required
def complaints():
    tickets = db.session.scalars(select(Complaint).where(Complaint.is_deleted.is_(False)).options(selectinload(Complaint.employee), selectinload(Complaint.category), selectinload(Complaint.assignment).selectinload(Assignment.technician)).order_by(Complaint.created_at.desc())).all()
    technicians = db.session.scalars(select(Technician).where(Technician.is_active.is_(True)).order_by(Technician.full_name)).all()
    history_by_ticket = {}
    for item in db.session.scalars(select(AssignmentHistory).options(selectinload(AssignmentHistory.technician), selectinload(AssignmentHistory.previous_technician), selectinload(AssignmentHistory.assigned_by)).order_by(AssignmentHistory.created_at.desc())).all():
        history_by_ticket.setdefault(item.complaint_id, []).append(item)
    return render_template("admin_complaints.html", complaints=tickets, technicians=technicians, history_by_ticket=history_by_ticket)


@admin_bp.post("/complaints/<int:complaint_id>/assignment")
@admin_required
def assign_complaint(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    technician = db.session.get(Technician, request.form.get("technician_id", type=int))
    if not complaint or complaint.deleted_at or not technician or not technician.is_active:
        flash("Select an active technician for an existing complaint.", "danger")
        return redirect(url_for("admin.complaints"))
    current, previous_id = complaint.assignment, complaint.assignment.technician_id if complaint.assignment else None
    if current and current.technician_id == technician.id:
        flash("That technician is already assigned to this complaint.", "info")
        return redirect(url_for("admin.complaints"))
    if current:
        current.technician_id, current.assigned_by_id, current.assigned_at, current.completed_at = technician.id, session["user_id"], datetime.utcnow(), None
    else:
        db.session.add(Assignment(complaint=complaint, technician=technician, assigned_by_id=session["user_id"]))
    db.session.add(AssignmentHistory(complaint_id=complaint.id, technician_id=technician.id, previous_technician_id=previous_id, assigned_by_id=session["user_id"], note=request.form.get("note", "").strip() or None))
    log_event(session["user_id"], "assign", "Complaint", complaint.id, {"technician_id": previous_id}, {"technician_id": technician.id})
    if complaint.status != "Assigned":
        try:
            transition_complaint(complaint, "Assigned", session["user_id"], "Assigned by administrator.")
        except ValueError:
            db.session.rollback()
            flash("A resolved or rejected complaint cannot be assigned. Create a new complaint instead.", "danger")
            return redirect(url_for("admin.complaints"))
    db.session.commit()
    sent = send_technician_assignment_email(technician, complaint, reassigned=previous_id is not None)
    flash(f"Complaint #{complaint.id} {'reassigned' if previous_id else 'assigned'} to {technician.full_name}." + (" Email sent." if sent else " Email could not be sent; assignment was saved."), "success" if sent else "warning")
    return redirect(url_for("admin.complaints"))


@admin_bp.post("/complaints/<int:complaint_id>/status")
@admin_required
def update_complaint_status(complaint_id):
    complaint, new_status = db.session.get(Complaint, complaint_id), request.form.get("status")
    if not complaint or complaint.deleted_at or new_status not in VALID_STATUSES:
        flash("Invalid complaint status update.", "danger")
    elif new_status in ACTIVE_STATUSES and not complaint.assignment:
        flash("Assign a technician before marking a complaint active.", "danger")
    elif complaint.status != new_status and can_transition(complaint.status, new_status):
        old_status = complaint.status
        transition_complaint(complaint, new_status, session["user_id"], request.form.get("note", "").strip() or "Updated by administrator on behalf of technician.")
        log_event(session["user_id"], "status_change", "Complaint", complaint.id, {"status": old_status}, {"status": new_status})
        if new_status in ("Resolved", "Rejected") and complaint.assignment:
            complaint.assignment.completed_at = datetime.utcnow()
        db.session.commit()
        flash(f"Complaint #{complaint.id} is now {new_status}.", "success")
    elif complaint.status == new_status:
        flash("The complaint already has that status.", "info")
    else:
        flash(f"Invalid workflow transition: {complaint.status} to {new_status}.", "danger")
    return redirect(url_for("admin.complaints"))


@admin_bp.post("/complaints/<int:complaint_id>/delete")
@admin_required
def delete_complaint(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if not complaint or complaint.is_deleted:
        flash("Complaint not found or already deleted.", "danger")
    else:
        complaint.is_deleted, complaint.deleted_at, complaint.deleted_by = True, datetime.utcnow(), session["user_id"]
        log_event(session["user_id"], "delete", "Complaint", complaint.id, {"is_deleted": False}, {"is_deleted": True})
        db.session.commit(); flash(f"Complaint #{complaint.id} moved to deleted records.", "success")
    return redirect(url_for("admin.complaints"))


@admin_bp.get("/complaints/deleted")
@admin_required
def deleted_complaints():
    records = db.session.scalars(select(Complaint).where(Complaint.is_deleted.is_(True)).options(selectinload(Complaint.employee)).order_by(Complaint.deleted_at.desc())).all()
    return render_template("admin_deleted_complaints.html", complaints=records)


@admin_bp.post("/complaints/<int:complaint_id>/restore")
@admin_required
def restore_complaint(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if not complaint or not complaint.is_deleted:
        flash("Deleted complaint not found.", "danger")
    else:
        complaint.is_deleted, complaint.deleted_at, complaint.deleted_by = False, None, None
        log_event(session["user_id"], "restore", "Complaint", complaint.id, {"is_deleted": True}, {"is_deleted": False})
        db.session.commit(); flash(f"Complaint #{complaint.id} restored.", "success")
    return redirect(url_for("admin.deleted_complaints"))


@admin_bp.get("/audit-logs")
@admin_required
def audit_logs():
    query = select(AuditLog).options(selectinload(AuditLog.user))
    if request.args.get("action"):
        query = query.where(AuditLog.action == request.args["action"])
    if request.args.get("entity"):
        query = query.where(AuditLog.entity == request.args["entity"])
    if request.args.get("user_id", type=int):
        query = query.where(AuditLog.user_id == request.args.get("user_id", type=int))
    logs = db.session.scalars(query.order_by(AuditLog.timestamp.desc()).limit(500)).all()
    return render_template("admin_audit_logs.html", logs=logs)


@admin_bp.route("/technicians", methods=["GET", "POST"])
@admin_required
def technicians():
    if request.method == "POST":
        data, error = _technician_form(), None
        error = _valid_technician(data)
        if error: flash(error, "danger")
        else:
            # specialization is retained for compatibility with the first schema.
            db.session.add(Technician(**data, specialization=data["skills"][:100])); db.session.commit()
            flash("Technician added. This does not create a login account.", "success")
        return redirect(url_for("admin.technicians"))
    records = db.session.scalars(select(Technician).options(selectinload(Technician.assignments).selectinload(Assignment.complaint)).order_by(Technician.full_name)).all()
    for technician in records:
        technician.active_ticket_count = sum(a.complaint.status in ACTIVE_STATUSES for a in technician.assignments)
    return render_template("admin_technicians.html", technicians=records, availability=AVAILABILITY)


@admin_bp.post("/technicians/<int:technician_id>/edit")
@admin_required
def edit_technician(technician_id):
    technician, data = db.session.get(Technician, technician_id), _technician_form()
    error = _valid_technician(data, technician_id)
    if not technician: flash("Technician not found.", "danger")
    elif error: flash(error, "danger")
    else:
        for field, value in data.items(): setattr(technician, field, value)
        technician.specialization = data["skills"][:100]
        technician.is_active = request.form.get("is_active") == "true"
        db.session.commit(); flash("Technician updated.", "success")
    return redirect(url_for("admin.technicians"))


@admin_bp.post("/technicians/<int:technician_id>/delete")
@admin_required
def delete_technician(technician_id):
    technician = db.session.get(Technician, technician_id)
    active_count = db.session.scalar(select(func.count(Assignment.id)).join(Complaint).where(Assignment.technician_id == technician_id, Complaint.status.in_(ACTIVE_STATUSES))) if technician else 0
    if not technician: flash("Technician not found.", "danger")
    elif active_count: flash("Reassign the technician's active tickets before deleting this record.", "danger")
    else:
        # Keep historical assignment records auditable; this is a soft delete.
        technician.is_active = False
        technician.availability = "Unavailable"
        db.session.commit(); flash("Technician removed from assignment lists; history is retained.", "success")
    return redirect(url_for("admin.technicians"))
