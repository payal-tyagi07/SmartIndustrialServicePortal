"""Add complaint soft deletion and expanded audit fields.

Revision ID: f51a4a883901
Revises: c3e991d2aa01
"""
from alembic import op
import sqlalchemy as sa

revision = "f51a4a883901"
down_revision = "c3e991d2aa01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("deleted_by", sa.Integer(), nullable=True))
        batch_op.create_index("ix_complaints_is_deleted", ["is_deleted"], unique=False)
        batch_op.create_index("ix_complaints_deleted_by", ["deleted_by"], unique=False)
        batch_op.create_foreign_key("fk_complaints_deleted_by", "users", ["deleted_by"], ["id"])
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column("actor_id", new_column_name="user_id")
        batch_op.alter_column("entity_type", new_column_name="entity")
        batch_op.alter_column("created_at", new_column_name="timestamp")
        batch_op.alter_column("details", new_column_name="old_value")
        batch_op.add_column(sa.Column("new_value", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("ip", sa.String(length=45), nullable=True))
        batch_op.drop_index("ix_audit_entity_created")
        batch_op.create_index("ix_audit_entity_created", ["entity", "entity_id", "timestamp"], unique=False)


def downgrade():
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_index("ix_audit_entity_created")
        batch_op.drop_column("ip")
        batch_op.drop_column("new_value")
        batch_op.alter_column("old_value", new_column_name="details")
        batch_op.alter_column("timestamp", new_column_name="created_at")
        batch_op.alter_column("entity", new_column_name="entity_type")
        batch_op.alter_column("user_id", new_column_name="actor_id")
        batch_op.create_index("ix_audit_entity_created", ["entity_type", "entity_id", "created_at"], unique=False)
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.drop_constraint("fk_complaints_deleted_by", type_="foreignkey")
        batch_op.drop_index("ix_complaints_deleted_by")
        batch_op.drop_index("ix_complaints_is_deleted")
        batch_op.drop_column("deleted_by")
        batch_op.drop_column("is_deleted")
