"""Scope transactions to users (requires an empty development database).

Revision ID: b21b30c40d50
Revises: a21b30c40d50
"""
from alembic import op
import sqlalchemy as sa

revision = "b21b30c40d50"
down_revision = "a21b30c40d50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("user_id", sa.Uuid(), nullable=False))
    op.create_foreign_key("fk_transactions_user", "transactions", "users", ["user_id"], ["id"])
    op.create_index("idx_transactions_user_time", "transactions", ["user_id", "occurred_at"])
    op.create_index("idx_transactions_user_category_time", "transactions", ["user_id", "category", "occurred_at"])


def downgrade() -> None:
    op.drop_index("idx_transactions_user_category_time", table_name="transactions")
    op.drop_index("idx_transactions_user_time", table_name="transactions")
    op.drop_constraint("fk_transactions_user", "transactions", type_="foreignkey")
    op.drop_column("transactions", "user_id")
