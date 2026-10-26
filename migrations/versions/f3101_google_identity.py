"""Add verified Google identities and encrypted per-user Calendar grants.

Revision ID: f3101
Revises: b21b30c40d50
"""
import sqlalchemy as sa
from alembic import op

revision = "f3101"
down_revision = "b21b30c40d50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "google_identities",
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False, unique=True),
    )
    op.create_table(
        "google_calendar_grants",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("google_calendar_grants")
    op.drop_table("google_identities")
