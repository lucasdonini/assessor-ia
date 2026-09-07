"""Create demo users.

Revision ID: a21b30c40d50
Revises: e1a128dd5d50
"""
from alembic import op
import sqlalchemy as sa

revision = "a21b30c40d50"
down_revision = "e1a128dd5d50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("users")
