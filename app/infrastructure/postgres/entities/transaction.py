from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.model.transaction import Category, TransactionType

from .base import Base


class TransactionORM(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.func.gen_random_uuid(),
    )

    user_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
    )

    amount: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False)

    category: Mapped[Category] = mapped_column(
        sa.Enum(Category, name="category_enum"),
        default=Category.OTHER,
        nullable=False,
    )

    transaction_type: Mapped[TransactionType] = mapped_column(
        sa.Enum(TransactionType, name="transaction_type_enum"),
        default=TransactionType.EXPENSE,
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    payment_method: Mapped[Optional[str]] = mapped_column(sa.String(32))

    occurred_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    source_text: Mapped[str] = mapped_column(sa.Text, nullable=False)

    is_canceled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.False_()
    )

    __table_args__ = (
        sa.Index("idx_transactions_user_time", "user_id", "occurred_at"),
        sa.Index(
            "idx_transactions_user_category_time", "user_id", "category", "occurred_at"
        ),
        sa.Index(
            "idx_transactions_occurred_at",
            "occurred_at",
        ),
        sa.Index(
            "idx_transactions_category_time",
            "category",
            "occurred_at",
        ),
    )
