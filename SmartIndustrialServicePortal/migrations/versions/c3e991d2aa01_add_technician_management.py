"""Add technician contact data and assignment history.

Revision ID: c3e991d2aa01
Revises: bb94878def10
"""
from alembic import op
import sqlalchemy as sa

revision = "c3e991d2aa01"
down_revision = "bb94878def10"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("technicians") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("department", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("skills", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("availability", sa.String(length=20), nullable=False, server_default="Available"))
        batch_op.create_index("ix_technicians_email", ["email"], unique=True)
        batch_op.create_index("ix_technicians_department", ["department"], unique=False)
        batch_op.create_index("ix_technicians_availability", ["availability"], unique=False)
    op.create_table(
        "assignment_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("complaint_id", sa.Integer(), nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_id", sa.Integer(), nullable=False),
        sa.Column("previous_technician_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"]),
        sa.ForeignKeyConstraint(["previous_technician_id"], ["technicians.id"]),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["users.id"]),
    )
    op.create_index("ix_assignment_history_complaint_created", "assignment_history", ["complaint_id", "created_at"])
    op.create_index("ix_assignment_history_technician_id", "assignment_history", ["technician_id"])
    op.create_index("ix_assignment_history_created_at", "assignment_history", ["created_at"])


def downgrade():
    op.drop_table("assignment_history")
    with op.batch_alter_table("technicians") as batch_op:
        batch_op.drop_index("ix_technicians_availability")
        batch_op.drop_index("ix_technicians_department")
        batch_op.drop_index("ix_technicians_email")
        batch_op.drop_column("availability")
        batch_op.drop_column("skills")
        batch_op.drop_column("department")
        batch_op.drop_column("email")
