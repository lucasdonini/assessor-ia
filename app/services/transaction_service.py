from datetime import date
from uuid import UUID

from app.application.exceptions import (
    MissingTransactionReferenceError,
    NoTransactionChangesError,
    TransactionNotFoundError,
)
from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.application.models.transaction_update import (
    UpdateTransactionParams,
)
from app.application.ports.logger import Logger, LoggerFactory
from app.application.repositories.transaction_repository import TransactionRepository
from app.domain.model.transaction import Transaction


class TransactionService:
    def __init__(
        self, repository: TransactionRepository, logger_factory: LoggerFactory
    ) -> None:
        self._repository = repository
        self._logger: Logger = logger_factory(__name__)

    async def calculate_total_balance(self, *, user_id: UUID) -> float:
        self._logger.debug("Calculating total balance")
        return await self._repository.get_balance(user_id=user_id)

    async def calculate_daily_balance(self, day: date, *, user_id: UUID) -> float:
        self._logger.debug(
            "Calculating daily balance",
            details={"day": str(day)},
        )
        return await self._repository.get_balance(day, user_id=user_id)

    async def search_transactions(
        self, params: TransactionQueryParams, *, user_id: UUID
    ) -> list[Transaction]:
        self._logger.debug(
            "Searching transactions",
            details={
                "filters": sorted(
                    key
                    for key, value in params.model_dump().items()
                    if value is not None and key != "source_text"
                )
            },
        )
        return await self._repository.find(params, user_id=user_id)

    async def add_transaction(
        self, transaction: Transaction, *, user_id: UUID
    ) -> Transaction:
        self._logger.debug(
            "Adding transaction",
            details={
                "category": transaction.category.value,
                "transaction_type": transaction.transaction_type.value,
            },
        )
        return await self._repository.add_transaction(transaction, user_id=user_id)

    async def update_transaction(
        self, params: UpdateTransactionParams, *, user_id: UUID
    ) -> Transaction:
        self._logger.debug(
            "Updating transaction",
            details={
                "updated_fields": sorted(
                    key
                    for key, value in params.model_dump(exclude={"query"}).items()
                    if value is not None
                )
            },
        )
        query = params.query
        has_reference = query.id is not None or (
            query.match_text is not None and query.date_local is not None
        )
        if not has_reference:
            raise MissingTransactionReferenceError
        if not params.has_update:
            raise NoTransactionChangesError

        transaction = await self._repository.update_transaction(params, user_id=user_id)
        if transaction is None:
            raise TransactionNotFoundError
        return transaction
