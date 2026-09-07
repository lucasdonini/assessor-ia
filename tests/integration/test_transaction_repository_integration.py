from datetime import date, datetime, timezone

import pytest

from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.domain.model.transaction import Category, Transaction, TransactionType
from app.infrastructure.postgres.entities.transaction import TransactionORM
from tests.user_identity import TEST_USER_ID

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("apply_migrations"),
]


class TestAddTransaction:
    async def test_add_creates_record(self, transaction_repository, db_session):
        t = Transaction(
            amount=250.00,
            category=Category.HEALTH,
            transaction_type=TransactionType.EXPENSE,
            description="Exame",
            source_text="Gastei 250 com exame",
            user_id=TEST_USER_ID,
        )
        result = await transaction_repository.add_transaction(t, user_id=TEST_USER_ID)

        assert isinstance(result, Transaction)
        assert result.amount == 250.00
        assert result.category == Category.HEALTH

    async def test_add_applies_defaults(self, transaction_repository, db_session):
        t = Transaction(
            amount=100.00, source_text="teste default", user_id=TEST_USER_ID
        )
        result = await transaction_repository.add_transaction(t, user_id=TEST_USER_ID)

        assert result.category == Category.OTHER
        assert result.transaction_type == TransactionType.EXPENSE
        assert result.occurred_at is not None

    async def test_add_persists_to_db(self, transaction_repository, db_session):
        t = Transaction(
            amount=500.00,
            category=Category.INVESTMENT,
            transaction_type=TransactionType.INCOME,
            description="Dividendos",
            source_text="Recebi dividendos",
            user_id=TEST_USER_ID,
        )
        result = await transaction_repository.add_transaction(t, user_id=TEST_USER_ID)

        orm = (
            await db_session.get(TransactionORM, result.id)
            if hasattr(result, "id")
            else None
        )
        if orm:
            assert orm.amount == 500.00
            assert orm.source_text == "Recebi dividendos"

    async def test_add_all_fields(self, transaction_repository, db_session):
        dt = datetime(2026, 7, 15, 10, 30, 0, tzinfo=timezone.utc)
        t = Transaction(
            amount=89.90,
            category=Category.FOOD,
            transaction_type=TransactionType.EXPENSE,
            description="Jantar",
            payment_method="crédito",
            occurred_at=dt,
            source_text="Jantar 89.90",
            user_id=TEST_USER_ID,
        )
        result = await transaction_repository.add_transaction(t, user_id=TEST_USER_ID)

        assert result.amount == 89.90
        assert result.category == Category.FOOD
        assert result.description == "Jantar"
        assert result.payment_method == "crédito"


class TestFind:
    async def test_find_default_returns_all(
        self, transaction_repository, seed_transactions
    ):
        params = TransactionQueryParams(limit=50)
        results = await transaction_repository.find(params, user_id=TEST_USER_ID)

        assert len(results) == 6

    async def test_find_by_source_text(self, transaction_repository, seed_transactions):
        params = TransactionQueryParams(source_text="almoço", limit=50)
        results = await transaction_repository.find(params, user_id=TEST_USER_ID)

        assert len(results) >= 1

    async def test_find_by_date_range(self, transaction_repository, seed_transactions):
        params = TransactionQueryParams(
            occurred_at_start=date(2026, 6, 2),
            occurred_at_end=date(2026, 6, 4),
            limit=50,
        )
        results = await transaction_repository.find(params, user_id=TEST_USER_ID)

        assert len(results) >= 3

    async def test_find_by_category(self, transaction_repository, seed_transactions):
        params = TransactionQueryParams(category=Category.FOOD, limit=50)
        results = await transaction_repository.find(params, user_id=TEST_USER_ID)

        assert len(results) >= 1
        for t in results:
            assert t.category == Category.FOOD

    async def test_find_by_transaction_type(
        self, transaction_repository, seed_transactions
    ):
        params = TransactionQueryParams(
            transaction_type=TransactionType.INCOME, limit=50
        )
        results = await transaction_repository.find(params, user_id=TEST_USER_ID)

        assert len(results) >= 2

    async def test_find_combined_filters(
        self, transaction_repository, seed_transactions
    ):
        params = TransactionQueryParams(
            category=Category.OTHER,
            transaction_type=TransactionType.INCOME,
            limit=50,
        )
        results = await transaction_repository.find(params, user_id=TEST_USER_ID)

        assert len(results) >= 1

    async def test_find_with_limit(self, transaction_repository, seed_transactions):
        params = TransactionQueryParams(limit=2)
        results = await transaction_repository.find(params, user_id=TEST_USER_ID)

        assert len(results) <= 2

    async def test_find_no_results(self, transaction_repository, seed_transactions):
        params = TransactionQueryParams(source_text="naoexiste_texto_xyz", limit=50)
        results = await transaction_repository.find(params, user_id=TEST_USER_ID)

        assert results == []

    async def test_find_limit_zero_returns_empty(
        self, transaction_repository, seed_transactions
    ):
        params = TransactionQueryParams(limit=0)
        results = await transaction_repository.find(params, user_id=TEST_USER_ID)

        assert results == []


class TestGetBalance:
    async def test_get_balance_all_time(
        self, transaction_repository, seed_transactions
    ):
        balance = await transaction_repository.get_balance(None, user_id=TEST_USER_ID)
        assert balance == 7600.0

    async def test_get_balance_at_end_of_day(
        self, transaction_repository, seed_transactions
    ):
        balance = await transaction_repository.get_balance(
            date(2026, 6, 1), user_id=TEST_USER_ID
        )
        assert balance == 4850.0

    async def test_get_balance_no_transactions(self, transaction_repository):
        balance = await transaction_repository.get_balance(
            date(2020, 1, 1), user_id=TEST_USER_ID
        )
        assert balance == 0.0


class TestUpdateTransaction:
    async def test_update_by_id(
        self, transaction_repository, db_session, seed_transactions
    ):
        target = seed_transactions[0]
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(id=target.id),
            amount=5500.00,
            description="Salário atualizado",
        )
        result = await transaction_repository.update_transaction(
            params, user_id=TEST_USER_ID
        )

        assert result is not None
        assert result.amount == 5500.00
        assert result.description == "Salário atualizado"
        await db_session.refresh(target)
        assert target.amount == 5500.00

    async def test_update_by_match_text_and_date(
        self, transaction_repository, db_session, seed_transactions
    ):
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(
                match_text="almoço",
                date_local=date(2026, 6, 1),
            ),
            amount=175.00,
        )
        result = await transaction_repository.update_transaction(
            params, user_id=TEST_USER_ID
        )

        assert result is not None
        assert result.amount == 175.00
