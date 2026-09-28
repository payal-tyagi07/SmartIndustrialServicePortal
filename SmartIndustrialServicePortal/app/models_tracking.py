from datetime import datetime
from app.extensions import db

class ComplaintComment(db.Model):
    __tablename__ = "complaint_comments"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = db.Column(db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    complaint = db.relationship("Complaint", back_populates="comments")
    author = db.relationship("User")
