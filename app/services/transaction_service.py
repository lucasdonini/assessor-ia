import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, replace
from datetime import date
from uuid import UUID

from app.application.exceptions import (
    ApplicationError,
    EvidenceRejectedError,
    FinancialOutcomeUnknownError,
    MissingTransactionReferenceError,
    NoTransactionChangesError,
    TransactionNotFoundError,
    UnsupportedCurrencyError,
)
from app.application.models.currency import FOREIGN, brl_statement
from app.application.models.evidence import FinancialExecution, JudgmentInput
from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.application.ports.evidence_validator import EvidenceValidator
from app.application.ports.logger import Logger, LoggerFactory
from app.application.repositories.transaction_repository import TransactionRepository
from app.domain.model.transaction import Transaction


class TransactionService:
    def __init__(
        self,
        repository: TransactionRepository,
        logger_factory: LoggerFactory,
        validator: EvidenceValidator | None = None,
    ) -> None:
        self._repository = repository
        self._logger: Logger = logger_factory(__name__)
        self._validator = validator

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
        self,
        transaction: Transaction,
        *,
        user_id: UUID,
        execution: FinancialExecution | None = None,
    ) -> Transaction:
        self._logger.debug(
            "Adding transaction",
            details={
                "category": transaction.category.value,
                "transaction_type": transaction.transaction_type.value,
            },
        )
        if transaction.user_id != user_id:
            raise EvidenceRejectedError
        if execution and execution.statements:
            source = brl_statement(execution.statements, transaction.amount)
            if source is not None:
                transaction = replace(transaction, source_text=source)
        return await self._mutate(
            "add",
            asdict(transaction),
            transaction.amount,
            user_id,
            execution,
            lambda: self._repository.add_transaction(transaction, user_id=user_id),
        )

    async def update_transaction(
        self,
        params: UpdateTransactionParams,
        *,
        user_id: UUID,
        execution: FinancialExecution | None = None,
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

        async def update() -> Transaction:
            transaction = await self._repository.update_transaction(
                params, user_id=user_id
            )
            if transaction is None:
                raise TransactionNotFoundError
            return transaction

        action = (
            "cancel"
            if params.is_canceled is True
            else "restore"
            if params.is_canceled is False
            else "update"
        )
        return await self._mutate(
            action,
            params.model_dump(mode="json", exclude_none=True),
            params.amount,
            user_id,
            execution,
            update,
        )

    async def _mutate(
        self,
        action: str,
        proposal: dict[str, object],
        amount: float | None,
        user_id: UUID,
        execution: FinancialExecution | None,
        operation: Callable[[], Awaitable[Transaction]],
    ) -> Transaction:
        if (
            execution is None
            or execution.user_id != user_id
            or not execution.statements
        ):
            raise EvidenceRejectedError
        fingerprint = json.dumps([action, proposal], default=str, sort_keys=True)
        async with execution.lock:
            previous = execution.results.get(fingerprint)
            if isinstance(previous, Transaction):
                return previous
            if execution.stopped:
                raise EvidenceRejectedError
            try:
                if (
                    amount is not None
                    and brl_statement(execution.statements, amount) is None
                ):
                    raise UnsupportedCurrencyError
                if self._validator is None:
                    raise EvidenceRejectedError
                evidence = []
                if action != "add":
                    target = await self._repository.resolve_transaction(
                        UpdateTransactionQuery.model_validate(proposal["query"]),
                        user_id=user_id,
                    )
                    if target is None:
                        raise TransactionNotFoundError
                    if amount is not None and FOREIGN.search(target.source_text):
                        raise UnsupportedCurrencyError
                    evidence.append(
                        {
                            "tool": "resolved_transaction",
                            "result": json.loads(
                                json.dumps(asdict(target), default=str)
                            ),
                        }
                    )
                result = await self._validator.validate(
                    JudgmentInput(
                        stage="command",
                        statements=execution.statements,
                        evidence=evidence,
                        candidate=json.dumps(
                            {"action": action, "fields": proposal}, default=str
                        ),
                    )
                )
                if not result.approved:
                    raise EvidenceRejectedError
                try:
                    transaction = await operation()
                except ApplicationError:
                    raise
                except Exception:
                    raise FinancialOutcomeUnknownError from None
                execution.results[fingerprint] = transaction
                execution.outcomes.append("confirmed")
                messages = {
                    "add": "Lançamento registrado em BRL.",
                    "update": "Lançamento atualizado.",
                    "cancel": "Lançamento cancelado.",
                    "restore": "Lançamento restaurado.",
                }
                execution.receipts.append(messages[action])
                return transaction
            except asyncio.CancelledError:
                execution.stopped = True
                raise
            except ApplicationError as exc:
                execution.stopped = True
                execution.outcomes.append(exc.code)
                execution.receipts.append(exc.public_message)
                raise
            except Exception:
                execution.stopped = True
                execution.outcomes.append("evidence_rejected")
                execution.receipts.append(EvidenceRejectedError.public_message)
                raise EvidenceRejectedError from None
