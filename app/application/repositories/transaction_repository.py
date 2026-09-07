from datetime import date
from typing import Protocol
from uuid import UUID

from app.application.models.transaction_query import TransactionQueryParams
from app.application.models.transaction_update import UpdateTransactionParams
from app.domain.model.transaction import Transaction


class TransactionRepository(Protocol):
    async def get_balance(self, day: date | None = None, *, user_id: UUID) -> float: ...

    async def find(
        self, params: TransactionQueryParams, *, user_id: UUID
    ) -> list[Transaction]: ...

    async def add_transaction(
        self, transaction: Transaction, *, user_id: UUID
    ) -> Transaction: ...

    async def update_transaction(
        self, params: UpdateTransactionParams, *, user_id: UUID
    ) -> Transaction | None: ...
