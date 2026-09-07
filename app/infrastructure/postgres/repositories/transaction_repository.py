import logging
from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import ScalarSelect, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.exceptions import AmbiguousTransactionError
from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.application.models.transaction_update import (
    UpdateTransactionParams,
)
from app.domain.model.transaction import Transaction, TransactionType
from app.infrastructure.postgres.entities.transaction import TransactionORM

logger = logging.getLogger(__name__)


class SQLAlchemyTransactionRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    def _orm_to_model(self, orm: TransactionORM) -> Transaction:
        return Transaction(
            id=orm.id,
            user_id=orm.user_id,
            amount=float(orm.amount),
            category=orm.category,
            transaction_type=orm.transaction_type,
            description=orm.description,
            payment_method=orm.payment_method,
            occurred_at=orm.occurred_at,
            updated_at=orm.updated_at,
            source_text=orm.source_text,
            is_canceled=orm.is_canceled,
        )

    def _model_to_orm(self, model: Transaction) -> TransactionORM:
        data = {
            "amount": model.amount,
            "user_id": model.user_id,
            "category": model.category,
            "transaction_type": model.transaction_type,
            "description": model.description,
            "payment_method": model.payment_method,
            "source_text": model.source_text,
            "is_canceled": model.is_canceled,
        }
        if model.id is not None:
            data["id"] = model.id
        if model.occurred_at is not None:
            data["occurred_at"] = model.occurred_at
        if model.updated_at is not None:
            data["updated_at"] = model.updated_at
        return TransactionORM(**data)

    def _build_sum_amounts_of_transaction_type_subquery(
        self,
        transaction_type: TransactionType,
        period_end: datetime | None,
        *,
        user_id: UUID,
    ) -> ScalarSelect[float]:
        stmt = select(func.coalesce(func.sum(TransactionORM.amount), 0)).where(
            TransactionORM.transaction_type == transaction_type,
            ~TransactionORM.is_canceled,
            TransactionORM.user_id == user_id,
        )

        if period_end:
            stmt = stmt.where(TransactionORM.occurred_at < period_end)

        return stmt.scalar_subquery()

    async def get_balance(self, day: date | None = None, *, user_id: UUID) -> float:
        "Returns the balance of the user at the end of the requested date"
        period_end = (
            datetime.combine(day + timedelta(days=1), time.min) if day else None
        )

        income = self._build_sum_amounts_of_transaction_type_subquery(
            transaction_type=TransactionType.INCOME,
            period_end=period_end,
            user_id=user_id,
        )

        expenses = self._build_sum_amounts_of_transaction_type_subquery(
            transaction_type=TransactionType.EXPENSE,
            period_end=period_end,
            user_id=user_id,
        )

        stmt = select(income - expenses)

        async with self._session_factory() as session:
            return float(await session.scalar(stmt) or 0)

    async def find(
        self, params: TransactionQueryParams, *, user_id: UUID
    ) -> list[Transaction]:
        logger.info(
            "Searching transactions",
            extra={"details": {"params": params.model_dump()}},
        )

        if params.limit is not None and params.limit <= 0:
            return []

        stmt = select(TransactionORM).where(TransactionORM.user_id == user_id)
        if params.source_text:
            stmt = stmt.where(
                TransactionORM.source_text.ilike(f"%{params.source_text}%")
            )
        if params.description:
            stmt = stmt.where(
                TransactionORM.description.ilike(f"%{params.description}%")
            )
        if params.occurred_at_start:
            stmt = stmt.where(TransactionORM.occurred_at >= params.occurred_at_start)
        if params.occurred_at_end:
            stmt = stmt.where(TransactionORM.occurred_at < params.occurred_at_end)
        if params.updated_at_start:
            stmt = stmt.where(TransactionORM.updated_at >= params.updated_at_start)
        if params.updated_at_end:
            stmt = stmt.where(TransactionORM.updated_at < params.updated_at_end)
        if params.category:
            stmt = stmt.where(TransactionORM.category == params.category)
        if params.is_canceled is not None:
            stmt = stmt.where(TransactionORM.is_canceled.is_(params.is_canceled))
        if params.transaction_type:
            stmt = stmt.where(
                TransactionORM.transaction_type == params.transaction_type
            )
        stmt = stmt.order_by(
            TransactionORM.occurred_at.asc()
            if params.occurred_at_start or params.occurred_at_end
            else TransactionORM.occurred_at.desc()
        )

        if params.limit is not None:
            stmt = stmt.limit(params.limit)

        logger.debug(
            "Query built",
            extra={"details": {"query": str(stmt)}},
        )
        result: list[Transaction]
        async with self._session_factory() as session:
            docs = (await session.scalars(stmt)).all()
            result = [self._orm_to_model(doc) for doc in docs]
        logger.info(
            "Search completed",
            extra={"details": {"count": len(result)}},
        )
        return result

    async def add_transaction(
        self, transaction: Transaction, *, user_id: UUID
    ) -> Transaction:
        if transaction.user_id != user_id:
            raise ValueError("Transaction owner does not match execution context")
        orm = self._model_to_orm(transaction)
        async with self._session_factory() as session:
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
        return self._orm_to_model(orm)

    async def update_transaction(
        self, params: UpdateTransactionParams, *, user_id: UUID
    ) -> Transaction | None:
        logger.info(
            "Updating transaction",
            extra={"details": {"params": params.model_dump()}},
        )

        stmt = select(TransactionORM).where(TransactionORM.user_id == user_id)
        if id := params.query.id:
            stmt = stmt.where(TransactionORM.id == id)
        elif (match_text := params.query.match_text) and (
            date_local := params.query.date_local
        ):
            period_start = datetime.combine(date_local, time.min)
            period_end = datetime.combine(date_local + timedelta(days=1), time.min)
            stmt = stmt.where(
                (
                    TransactionORM.source_text.ilike(f"%{match_text}%")
                    | TransactionORM.description.ilike(f"%{match_text}%")
                ),
                TransactionORM.occurred_at >= period_start,
                TransactionORM.occurred_at < period_end,
            )
        else:
            raise AssertionError("Update command must contain a valid reference")

        stmt = stmt.order_by(TransactionORM.occurred_at.desc()).limit(2)
        to_update = params.model_dump(
            exclude_none=True,
            exclude={"query"},
        )

        logger.debug(
            "Locating update target",
            extra={"details": {"query": str(stmt)}},
        )
        async with self._session_factory() as session:
            targets = (await session.scalars(stmt)).all()

            if not targets:
                return None
            if len(targets) > 1:
                raise AmbiguousTransactionError
            target = targets[0]

            for attr, val in to_update.items():
                setattr(target, attr, val)
            await session.commit()
            await session.refresh(target)

            logger.debug(
                "Transaction updated",
                extra={"details": {"updated_id": target.id}},
            )
            return self._orm_to_model(target)
