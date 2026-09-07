from datetime import date

import pytest
from pydantic import ValidationError

from app.application.exceptions import (
    NoTransactionChangesError,
    TransactionNotFoundError,
)
from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.domain.model.transaction import Category, Transaction, TransactionType
from tests.user_identity import TEST_USER_ID

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("apply_migrations"),
]


class TestCalculateTotalBalance:
    async def test_positive_balance(self, transaction_service, seed_transactions):
        balance = await transaction_service.calculate_total_balance(
            user_id=TEST_USER_ID
        )
        # INCOME(5000+3000) - EXPENSE(150+50+200) = 8000 - 400 = 7600
        assert balance == 7600.00

    async def test_zero_balance_no_transactions(
        self, transaction_repository, db_session, mock_logger
    ):
        from app.services.transaction_service import TransactionService

        service = TransactionService(
            repository=transaction_repository,
            logger=mock_logger,
        )
        balance = await service.calculate_total_balance(user_id=TEST_USER_ID)
        assert balance == 0.0


class TestCalculateDailyBalance:
    async def test_daily_balance(self, transaction_service, seed_transactions):
        balance = await transaction_service.calculate_daily_balance(
            date(2026, 6, 1), user_id=TEST_USER_ID
        )
        # INCOME(5000) - EXPENSE(150) = 4850
        assert balance == 4850.00

    async def test_daily_balance_another_day(
        self, transaction_service, seed_transactions
    ):
        balance = await transaction_service.calculate_daily_balance(
            date(2026, 6, 2), user_id=TEST_USER_ID
        )
        # Acumulado até 02/06: INCOME(5000+3000) - EXPENSE(150+50) = 7800
        assert balance == 7800.00

    async def test_daily_balance_no_transactions(
        self, transaction_repository, db_session, mock_logger
    ):
        from app.services.transaction_service import TransactionService

        service = TransactionService(
            repository=transaction_repository,
            logger=mock_logger,
        )
        balance = await service.calculate_daily_balance(
            date(2026, 1, 1), user_id=TEST_USER_ID
        )
        assert balance == 0.0


class TestSearchTransactions:
    async def test_search_by_category(self, transaction_service, seed_transactions):
        params = TransactionQueryParams(category=Category.HEALTH, limit=50)
        results = await transaction_service.search_transactions(
            params, user_id=TEST_USER_ID
        )
        assert len(results) >= 1
        for t in results:
            assert t.category == Category.HEALTH

    async def test_search_all(self, transaction_service, seed_transactions):
        params = TransactionQueryParams(limit=50)
        results = await transaction_service.search_transactions(
            params, user_id=TEST_USER_ID
        )
        assert len(results) == 6


class TestAddTransaction:
    async def test_add_and_retrieve(self, transaction_service, db_session):
        t = Transaction(
            amount=300.00,
            category=Category.BILLS,
            transaction_type=TransactionType.EXPENSE,
            description="Conta de luz",
            source_text="Paguei conta de luz",
            user_id=TEST_USER_ID,
        )
        result = await transaction_service.add_transaction(t, user_id=TEST_USER_ID)

        assert result.amount == 300.00
        assert result.category == Category.BILLS


class TestUpdateTransaction:
    async def test_update(self, transaction_service, seed_transactions):
        target = seed_transactions[0]
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(id=target.id),
            amount=5200.00,
        )
        result = await transaction_service.update_transaction(
            params, user_id=TEST_USER_ID
        )

        assert result is not None
        assert result.amount == 5200.00

    async def test_update_no_match(self, transaction_service, seed_transactions):
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(
                match_text="inexistente",
                date_local=date(2026, 6, 1),
            ),
            amount=100.00,
        )
        with pytest.raises(TransactionNotFoundError):
            await transaction_service.update_transaction(params, user_id=TEST_USER_ID)

    async def test_update_without_changes(self, transaction_service, seed_transactions):
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(id=seed_transactions[0].id),
        )
        with pytest.raises(NoTransactionChangesError):
            await transaction_service.update_transaction(params, user_id=TEST_USER_ID)

    async def test_update_no_reference(self, transaction_service):
        with pytest.raises(ValidationError):
            UpdateTransactionQuery()
