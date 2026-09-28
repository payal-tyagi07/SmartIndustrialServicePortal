from datetime import datetime, timedelta
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func, select
from app.extensions import db
from app.models import Attachment, Category, Complaint, StatusHistory
from app.decorators import employee_required
from app.services.ai_service import complaint_draft
from app.services.uploads import save_attachment

employee_bp = Blueprint("employee", __name__)
CATEGORY_NAMES = ("IT Support", "Electrical", "Water Supply", "Equipment Repair", "Safety Issue", "Housekeeping", "Network Problem", "Others")

def _categories():
    records = {item.name: item for item in db.session.scalars(select(Category)).all()}
    for name in CATEGORY_NAMES:
        if name not in records:
            records[name] = Category(name=name); db.session.add(records[name])
    db.session.commit()
    return [records[name] for name in CATEGORY_NAMES]


@employee_bp.get("/dashboard")
@employee_required
def dashboard():
    tickets = db.session.scalars(select(Complaint).where(Complaint.employee_id == session.get("user_id"), Complaint.status != "Draft").order_by(Complaint.created_at.desc()).limit(5)).all()
    return render_template("employee_dashboard.html", recent_complaints=tickets, stats={})

@employee_bp.route("/raise_complaint", methods=["GET", "POST"])
@employee_required
def raise_complaint():
    category_list = _categories()
    draft_id = request.args.get("draft", type=int)
    draft = db.session.scalar(select(Complaint).where(Complaint.id == draft_id, Complaint.employee_id == session["user_id"], Complaint.status == "Draft")) if draft_id else None
    if request.method == "GET":
        return render_template("raise_complaint.html", categories=category_list, draft=draft)
    names = ("title", "category", "priority", "location", "department", "equipment_serial_number", "symptoms", "operational_impact", "description")
    data = {name: request.form.get(name, "").strip() for name in names}
    action = request.form.get("action")
    missing = [name for name in ("title", "category", "priority", "location", "department", "symptoms", "operational_impact") if not data[name]]
    if missing or data["category"] not in CATEGORY_NAMES or data["priority"] not in ("Low", "Medium", "High", "Critical") or (action == "submit" and not data["description"]):
        flash("Complete all required fields and review the description before submitting.", "danger")
        return render_template("raise_complaint.html", categories=category_list, draft=draft, form=data), 400
    category = next(item for item in category_list if item.name == data["category"])
    duplicate = db.session.scalar(select(Complaint).where(Complaint.employee_id == session["user_id"], func.lower(Complaint.title) == data["title"].lower(), Complaint.status.not_in(("Draft", "Resolved", "Rejected")), Complaint.created_at >= datetime.utcnow() - timedelta(days=7)))
    if action == "submit" and duplicate and request.form.get("allow_duplicate") != "true":
        flash(f"Similar active request #{duplicate.id} found. Confirm only if this is separate.", "warning")
        return render_template("raise_complaint.html", categories=category_list, draft=draft, form=data, duplicate=duplicate), 409
    complaint = draft or Complaint(employee_id=session["user_id"], category=category, **data)
    for name, value in data.items(): setattr(complaint, name, value)
    complaint.category, complaint.status = category, ("Draft" if action == "draft" else "Pending")
    if not draft: db.session.add(complaint)
    db.session.flush()
    if action == "submit":
        try: stored = save_attachment(request.files.get("attachment"))
        except ValueError as error:
            db.session.rollback(); flash(str(error), "danger"); return render_template("raise_complaint.html", categories=category_list, form=data), 400
        if stored: db.session.add(Attachment(complaint=complaint, stored_name=stored, original_name=request.files["attachment"].filename, mime_type=request.files["attachment"].mimetype or "application/octet-stream"))
        db.session.add(StatusHistory(complaint=complaint, changed_by_id=session["user_id"], new_status="Pending", note="Submitted by employee."))
    db.session.commit()
    if action == "draft":
        flash("Draft saved.", "success"); return redirect(url_for("employee.raise_complaint", draft=complaint.id))
    flash(f"Service request #{complaint.id} submitted.", "success"); return redirect(url_for("employee.dashboard"))

@employee_bp.post("/api/description-draft")
@employee_required
def generate_description_draft():
    payload = request.get_json(silent=True) or {}
    title, category = str(payload.get("title", "")).strip(), str(payload.get("category", "")).strip()
    if not title or category not in CATEGORY_NAMES: return jsonify(error="Enter a title and category first."), 400
    return jsonify(description=complaint_draft(title, category))
