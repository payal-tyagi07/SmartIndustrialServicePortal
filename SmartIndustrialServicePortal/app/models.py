from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (db.CheckConstraint("role IN ('employee', 'admin')", name="ck_user_role"),)

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=True, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    department = db.Column(db.String(100), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, index=True)  # employee or admin only
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    failed_login_count = db.Column(db.SmallInteger, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True, index=True)
    password_changed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_enabled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    complaints = db.relationship("Complaint", back_populates="employee", foreign_keys="Complaint.employee_id")
    feedback_items = db.relationship("Feedback", back_populates="employee")
    audit_events = db.relationship("AuditLog", back_populates="actor")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = datetime.utcnow()

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    complaints = db.relationship("Complaint", back_populates="category")


class Technician(db.Model):
    """Admin-managed master data, deliberately not a User and never authenticated."""
    __tablename__ = "technicians"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False)
    department = db.Column(db.String(100), nullable=False, index=True)
    skills = db.Column(db.Text, nullable=False)
    availability = db.Column(db.String(20), nullable=False, default="Available", index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    assignments = db.relationship("Assignment", back_populates="technician")
    assignment_history = db.relationship("AssignmentHistory", back_populates="technician", foreign_keys="AssignmentHistory.technician_id")


class Complaint(db.Model):
    __tablename__ = "complaints"
    __table_args__ = (
        db.CheckConstraint("priority IN ('Low', 'Medium', 'High', 'Critical')", name="ck_complaint_priority"),
        db.CheckConstraint("status IN ('Draft', 'Pending', 'Assigned', 'In Progress', 'Resolved', 'Rejected')", name="ck_complaint_status"),
        db.Index("ix_complaint_status_priority_created", "status", "priority", "created_at"),
        db.Index("ix_complaint_employee_created", "employee_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.ForeignKey("categories.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(255), nullable=False)
    reported_department = db.Column(db.String(100), nullable=False, index=True)
    equipment_serial_number = db.Column(db.String(150))
    symptoms = db.Column(db.Text, nullable=False)
    operational_impact = db.Column(db.Text, nullable=False)
    admin_notes = db.Column(db.Text)
    eta_at = db.Column(db.DateTime)
    sla_due_at = db.Column(db.DateTime, index=True)
    priority = db.Column(db.String(20), nullable=False, default="Medium", index=True)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    employee = db.relationship("User", back_populates="complaints", foreign_keys=[employee_id])
    category = db.relationship("Category", back_populates="complaints")
    assignment = db.relationship("Assignment", back_populates="complaint", uselist=False, cascade="all, delete-orphan")
    status_history = db.relationship("StatusHistory", back_populates="complaint", cascade="all, delete-orphan")
    attachments = db.relationship("Attachment", back_populates="complaint", cascade="all, delete-orphan")
    comments = db.relationship("ComplaintComment", back_populates="complaint", cascade="all, delete-orphan")


class Assignment(db.Model):
    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.ForeignKey("complaints.id", ondelete="CASCADE"), unique=True, nullable=False)
    technician_id = db.Column(db.ForeignKey("technicians.id"), nullable=False, index=True)
    assigned_by_id = db.Column(db.ForeignKey("users.id"), nullable=False)
    assigned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    complaint = db.relationship("Complaint", back_populates="assignment")
    technician = db.relationship("Technician", back_populates="assignments")
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_id])


class AssignmentHistory(db.Model):
    """An immutable record for every assignment and reassignment made by an admin."""
    __tablename__ = "assignment_history"
    __table_args__ = (db.Index("ix_assignment_history_complaint_created", "complaint_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    technician_id = db.Column(db.ForeignKey("technicians.id"), nullable=False, index=True)
    assigned_by_id = db.Column(db.ForeignKey("users.id"), nullable=False)
    previous_technician_id = db.Column(db.ForeignKey("technicians.id"), nullable=True)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    complaint = db.relationship("Complaint", foreign_keys=[complaint_id])
    technician = db.relationship("Technician", foreign_keys=[technician_id], back_populates="assignment_history")
    previous_technician = db.relationship("Technician", foreign_keys=[previous_technician_id])
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_id])


class StatusHistory(db.Model):
    __tablename__ = "status_history"
    __table_args__ = (db.Index("ix_status_history_complaint_created", "complaint_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    changed_by_id = db.Column(db.ForeignKey("users.id"), nullable=False)
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20), nullable=False, index=True)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    complaint = db.relationship("Complaint", back_populates="status_history")
    changed_by = db.relationship("User", foreign_keys=[changed_by_id])


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    stored_name = db.Column(db.String(255), nullable=False, unique=True)
    original_name = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    storage_path = db.Column(db.String(500), nullable=False)
    thumbnail_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    complaint = db.relationship("Complaint", back_populates="attachments")


class Feedback(db.Model):
    __tablename__ = "feedback"
    __table_args__ = (db.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),)

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = db.Column(db.SmallInteger, nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_reviewed = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    employee = db.relationship("User", back_populates="feedback_items")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (db.Index("ix_audit_entity_created", "entity_type", "entity_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    actor = db.relationship("User", back_populates="audit_events")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship("User", back_populates="notifications")


# Register optional tracking tables with the same SQLAlchemy metadata.
from app.models_tracking import ComplaintComment  # noqa: E402,F401
