"""Persist owned events and durable creation proposals/receipts.

Revision ID: f3102
Revises: f3101
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "f3102"
down_revision = "f3101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(1000)),
        sa.Column("notes", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("end_time > start_time", name="ck_events_interval"),
    )
    op.create_index("ix_events_owner_start", "events", ["user_id", "start_time", "id"])
    op.create_table(
        "event_operations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("result", JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_event_operations_owner", "event_operations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_event_operations_owner", table_name="event_operations")
    op.drop_table("event_operations")
    op.drop_index("ix_events_owner_start", table_name="events")
    op.drop_table("events")
