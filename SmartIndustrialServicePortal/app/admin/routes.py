print(">>> app/admin/routes.py LOADED <<<")

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from werkzeug.security import check_password_hash
from app.models import Category, Feedback

from app.decorators import admin_required
from app.extensions import db
from app.models import Assignment, AssignmentHistory, AuditLog, Complaint, StatusHistory, Technician, User
from app.services.email_service import send_technician_assignment_email
from app.services.workflow_service import can_transition, transition_complaint
from app.services.audit_service import log_event

admin_bp = Blueprint("admin", __name__)
ACTIVE_STATUSES = ("Assigned", "In Progress")
VALID_STATUSES = ("Pending", "Assigned", "In Progress", "Resolved", "Rejected")
AVAILABILITY = ("Available", "Busy", "Unavailable")


# ─────────────────────────────────────────────────────────
# AUTH (login / logout) — MISSING before, now added
# ─────────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    print(">>> admin_login() CALLED <<<")
    if request.method == "POST":
        identifier = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        # Try to find user by email first
        user = db.session.scalar(select(User).where(User.email == identifier))

        # Fallback: literal "admin" finds any admin account
        if not user and identifier.lower() == "admin":
            user = db.session.scalar(select(User).where(User.role == "admin").limit(1))

        if not user:
            flash("Invalid credentials.", "danger")
            return render_template("admin_login.html"), 401

        # Verify password (use whatever your model exposes)
        password_ok = check_password_hash(user.password_hash, password)
        print(f"[ADMIN LOGIN] password_hash_prefix={user.password_hash[:40] if user.password_hash else 'EMPTY'}")
        print(f"[ADMIN LOGIN] password_ok={password_ok}")

        if not password_ok:
            flash("Invalid credentials.", "danger")
            return render_template("admin_login.html"), 401

        if (user.role or "").lower() != "admin":
            flash("You do not have admin privileges.", "danger")
            return render_template("admin_login.html"), 403

        session["user_id"] = user.id
        session["role"] = "admin"
        session["name"] = getattr(user, "full_name", None) or getattr(user, "name", "Admin")

        log_event(user.id, "login", "User", user.id, None, {"role": "admin"})
        return redirect(url_for("admin.dashboard"))

    return render_template("admin_login.html")


@admin_bp.get("/logout")
def admin_logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("admin.admin_login"))


# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────
# DASHBOARD / ANALYTICS
# ─────────────────────────────────────────────────────────

@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    from sqlalchemy import func

    # Fetch all complaints (non-deleted for stats)
    all_complaints = db.session.scalars(
        select(Complaint).where(Complaint.is_deleted.is_(False))
        .options(
            selectinload(Complaint.employee),
            selectinload(Complaint.category),
            selectinload(Complaint.assignment).selectinload(Assignment.technician),
        )
        .order_by(Complaint.created_at.desc())
    ).all()

    # Compute stats
    stats = {
        "total": len(all_complaints),
        "pending": sum(c.status == "Pending" for c in all_complaints),
        "assigned": sum(c.status == "Assigned" for c in all_complaints),
        "in_progress": sum(c.status == "In Progress" for c in all_complaints),
        "resolved": sum(c.status == "Resolved" for c in all_complaints),
        "rejected": sum(c.status == "Rejected" for c in all_complaints),
        "critical": sum(c.priority == "Critical" for c in all_complaints),
    }

    # Recent 10 for the table
    recent = all_complaints[:10]

    return render_template(
        "admin_dashboard.html",
        complaints=all_complaints,
        recent_complaints=recent,
        stats=stats,
    )


@admin_bp.get("/analytics")
@admin_required
def analytics():
    query = select(Complaint).where(Complaint.is_deleted.is_(False)).options(selectinload(Complaint.assignment).selectinload(Assignment.technician))
    start, end = request.args.get("start"), request.args.get("end")
    department, technician_id = request.args.get("department"), request.args.get("technician_id", type=int)
    if start:
        query = query.where(Complaint.created_at >= datetime.fromisoformat(start))
    if end:
        query = query.where(Complaint.created_at < datetime.fromisoformat(end).replace(hour=23, minute=59, second=59))
    if department:
        query = query.where(Complaint.reported_department == department)
    if technician_id:
        query = query.join(Assignment).where(Assignment.technician_id == technician_id)
    tickets = db.session.scalars(query).all()
    resolved = [t for t in tickets if t.status == "Resolved" and t.assignment and t.assignment.completed_at]
    mttr_hours = round(sum((t.assignment.completed_at - t.created_at).total_seconds() / 3600 for t in resolved) / len(resolved), 2) if resolved else 0
    sla_checked = [t for t in resolved if t.sla_due_at]
    sla_percent = round(100 * sum(t.assignment.completed_at <= t.sla_due_at for t in sla_checked) / len(sla_checked), 1) if sla_checked else 0
    performance = {}
    for ticket in tickets:
        if ticket.assignment:
            row = performance.setdefault(ticket.assignment.technician.full_name, {"resolved": 0, "active": 0})
            row["resolved" if ticket.status == "Resolved" else "active"] += 1
    months, heatmap, hotspots = {}, {}, {}
    for ticket in tickets:
        months[ticket.created_at.strftime("%Y-%m")] = months.get(ticket.created_at.strftime("%Y-%m"), 0) + 1
        heatmap.setdefault(ticket.reported_department, {}).setdefault(ticket.status, 0)
        heatmap[ticket.reported_department][ticket.status] += 1
        if ticket.priority == "Critical":
            hotspots[ticket.location] = hotspots.get(ticket.location, 0) + 1
    analytics_data = {
        "mttr_hours": mttr_hours, "sla_percent": sla_percent,
        "performance": [{"name": name, **values} for name, values in sorted(performance.items(), key=lambda item: (-item[1]["resolved"], item[1]["active"]))],
        "months": dict(sorted(months.items())), "heatmap": heatmap,
        "hotspots": dict(sorted(hotspots.items(), key=lambda item: item[1], reverse=True)[:10]),
    }
    departments = db.session.scalars(select(Complaint.reported_department).where(Complaint.is_deleted.is_(False)).distinct().order_by(Complaint.reported_department)).all()
    technicians = db.session.scalars(select(Technician).order_by(Technician.full_name)).all()
    return render_template("admin_analytics.html", data=analytics_data, departments=departments, technicians=technicians)


# ─────────────────────────────────────────────────────────
# COMPLAINTS
# ─────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────
# TECHNICIANS
# ─────────────────────────────────────────────────────────

@admin_bp.route("/technicians", methods=["GET", "POST"])
@admin_required
def technicians():
    if request.method == "POST":
        data, error = _technician_form(), None
        error = _valid_technician(data)
        if error: flash(error, "danger")
        else:
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
        technician.is_active = False
        technician.availability = "Unavailable"
        db.session.commit(); flash("Technician removed from assignment lists; history is retained.", "success")
    return redirect(url_for("admin.technicians"))


# ─────────────────────────────────────────────────────────
# EMPLOYEE FEEDBACK
# ─────────────────────────────────────────────────────────

@admin_bp.get("/feedback")
@admin_required
def feedback():
    from app.models import Feedback
    items = db.session.scalars(
        select(Feedback)
        .options(selectinload(Feedback.employee))
        .order_by(Feedback.created_at.desc())
    ).all()
    avg = round(sum(f.rating for f in items) / len(items), 2) if items else 0
    return render_template("admin_feedback.html", feedback=items, average=avg)


# ─────────────────────────────────────────────────────────
# EMPLOYEE LIST
# ─────────────────────────────────────────────────────────

@admin_bp.get("/employees")
@admin_required
def employees():
    from app.models import Feedback
    staff = db.session.scalars(
        select(User).where(User.role == "employee").order_by(User.full_name)
    ).all()
    return render_template("admin_employees.html", employees=staff)


# ─────────────────────────────────────────────────────────
# REPORTS
# ─────────────────────────────────────────────────────────

@admin_bp.get("/reports")
@admin_required
def reports():
    query = select(Complaint).where(Complaint.is_deleted.is_(False)).options(
        selectinload(Complaint.employee),
        selectinload(Complaint.category),
        selectinload(Complaint.assignment).selectinload(Assignment.technician),
    )

    start = request.args.get("start")
    end = request.args.get("end")
    department = request.args.get("department")
    status = request.args.get("status")
    priority = request.args.get("priority")
    category_name = request.args.get("category")

    if start:
        query = query.where(Complaint.created_at >= datetime.fromisoformat(start))
    if end:
        query = query.where(Complaint.created_at < datetime.fromisoformat(end).replace(hour=23, minute=59, second=59))
    if department:
        query = query.where(Complaint.reported_department == department)
    if status:
        query = query.where(Complaint.status == status)
    if priority:
        query = query.where(Complaint.priority == priority)
    if category_name:
        query = query.join(Complaint.category).where(Category.name == category_name)

    tickets = db.session.scalars(query.order_by(Complaint.created_at.desc())).all()

    # Distinct values for filter dropdowns
    departments = db.session.scalars(
        select(Complaint.reported_department).where(Complaint.is_deleted.is_(False)).distinct()
    ).all()
    categories = db.session.scalars(select(Category).order_by(Category.name)).all()

    return render_template(
        "admin_reports.html",
        complaints=tickets,
        departments=departments,
        categories=categories,
        filters=request.args,
    )


@admin_bp.get("/reports/export.csv")
@admin_required
def export_reports_csv():
    import csv
    from io import StringIO
    from flask import Response

    query = select(Complaint).where(Complaint.is_deleted.is_(False)).options(
        selectinload(Complaint.employee),
        selectinload(Complaint.category),
    )
    if request.args.get("status"):
        query = query.where(Complaint.status == request.args["status"])
    if request.args.get("priority"):
        query = query.where(Complaint.priority == request.args["priority"])
    if request.args.get("department"):
        query = query.where(Complaint.reported_department == request.args["department"])

    tickets = db.session.scalars(query.order_by(Complaint.created_at.desc())).all()

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Title", "Employee", "Department", "Category", "Priority", "Status", "Created"])
    for t in tickets:
        writer.writerow([
            t.id, t.title,
            t.employee.full_name if t.employee else "",
            t.reported_department or "",
            t.category.name if t.category else "",
            t.priority, t.status,
            t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
        ])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=complaints_report.csv"},
    )    