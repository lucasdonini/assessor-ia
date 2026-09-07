from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.exceptions import AmbiguousTransactionError
from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.domain.model.transaction import Category, Transaction, TransactionType
from tests.user_identity import TEST_USER_ID

pytestmark = pytest.mark.asyncio


class TestGetBalance:
    async def test_get_balance_no_date(self, repository, mock_session):
        mock_session.scalar.return_value = 7600.0

        result = await repository.get_balance(None, user_id=TEST_USER_ID)

        assert result == 7600.0

    async def test_get_balance_with_date(self, repository, mock_session):
        mock_session.scalar.return_value = 4850.0

        result = await repository.get_balance(date(2026, 6, 1), user_id=TEST_USER_ID)

        assert result == 4850.0

    async def test_get_balance_scalar_none_returns_zero(
        self,
        repository,
        mock_session,
    ):
        mock_session.scalar.return_value = None

        result = await repository.get_balance(date(2020, 1, 1), user_id=TEST_USER_ID)

        assert result == 0.0


class TestFind:
    async def test_find_with_params(self, repository, mock_session):

        params = TransactionQueryParams(
            source_text="almoço",
            category=Category.FOOD,
            limit=10,
        )
        mock_session.scalars.return_value.all.return_value = []

        result = await repository.find(params, user_id=TEST_USER_ID)

        assert result == []

    async def test_find_empty_no_results(self, repository, mock_session):
        params = TransactionQueryParams(source_text="inexistente")
        mock_session.scalars.return_value.all.return_value = []

        result = await repository.find(params, user_id=TEST_USER_ID)

        assert result == []

    async def test_find_limit_zero(self, repository, mock_session):
        params = TransactionQueryParams(limit=0)

        result = await repository.find(params, user_id=TEST_USER_ID)

        assert result == []
        mock_session.scalars.assert_not_called()

    async def test_find_returns_correct_amount(self, repository, mock_session):
        orm_objects = []
        for i in range(3):
            orm = MagicMock()
            orm.amount = 100.0 * (i + 1)
            orm.category = Category.FOOD
            orm.transaction_type = TransactionType.EXPENSE
            orm.source_text = f"test {i}"
            orm.id = uuid4()
            orm.occurred_at = datetime.now(timezone.utc)
            orm.description = "desc"
            orm.payment_method = "pix"
            orm.updated_at = datetime.now(timezone.utc)
            orm_objects.append(orm)
        mock_session.scalars.return_value.all.return_value = orm_objects
        params = TransactionQueryParams(limit=50)

        result = await repository.find(params, user_id=TEST_USER_ID)

        assert len(result) == 3
        for t in result:
            assert isinstance(t, Transaction)

    async def test_find_applies_limit(self, repository, mock_session):
        params = TransactionQueryParams(limit=5)
        mock_session.scalars.return_value.all.return_value = []

        await repository.find(params, user_id=TEST_USER_ID)

        stmt = mock_session.scalars.call_args[0][0]
        assert stmt._limit == 5

    async def test_find_orders_by_occurred_at_desc_by_default(
        self, repository, mock_session
    ):
        params = TransactionQueryParams(limit=10)
        mock_session.scalars.return_value.all.return_value = []

        await repository.find(params, user_id=TEST_USER_ID)

        stmt = mock_session.scalars.call_args[0][0]
        order_by_clauses = stmt._order_by_clauses
        assert any("occurred_at" in str(c) for c in order_by_clauses)


class TestAddTransaction:
    async def test_add_transaction(self, repository, mock_session, sample_transaction):
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None

        result = await repository.add_transaction(
            sample_transaction, user_id=TEST_USER_ID
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        assert isinstance(result, Transaction)

    async def test_add_calls_session_commit_and_refresh(
        self, repository, mock_session, sample_transaction
    ):
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None

        await repository.add_transaction(sample_transaction, user_id=TEST_USER_ID)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    async def test_add_raises_exception(
        self, repository, mock_session, sample_transaction
    ):
        mock_session.add.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            await repository.add_transaction(sample_transaction, user_id=TEST_USER_ID)


class TestUpdateTransaction:
    async def test_update_by_id(self, repository, mock_session):
        target_id = uuid4()
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(id=target_id),
            amount=200.0,
            category=Category.HEALTH,
        )
        mock_orm = MagicMock()
        mock_orm.amount = 100.0
        mock_orm.category = Category.FOOD
        mock_orm.transaction_type = TransactionType.EXPENSE
        mock_orm.source_text = "original"
        mock_orm.id = target_id
        mock_orm.occurred_at = datetime.now(timezone.utc)
        mock_orm.description = "old"
        mock_orm.payment_method = "cash"
        mock_orm.updated_at = datetime.now(timezone.utc)
        mock_session.scalar.return_value = mock_orm
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None
        mock_session.scalars.return_value.all.return_value = [mock_orm]

        result = await repository.update_transaction(params, user_id=TEST_USER_ID)

        assert result is not None
        assert isinstance(result, Transaction)
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    async def test_update_by_match_text(self, repository, mock_session):
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(
                match_text="almoço",
                date_local=date(2026, 6, 1),
            ),
            amount=150.0,
        )
        mock_orm = MagicMock()
        mock_orm.amount = 100.0
        mock_orm.category = Category.FOOD
        mock_orm.transaction_type = TransactionType.EXPENSE
        mock_orm.source_text = "almoço"
        mock_orm.id = uuid4()
        mock_orm.occurred_at = datetime.now(timezone.utc)
        mock_orm.description = "old"
        mock_orm.payment_method = "cash"
        mock_orm.updated_at = datetime.now(timezone.utc)
        mock_session.scalar.return_value = mock_orm
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None
        mock_session.scalars.return_value.all.return_value = [mock_orm]

        result = await repository.update_transaction(params, user_id=TEST_USER_ID)

        assert result is not None
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    async def test_update_not_found_returns_none(self, repository, mock_session):
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(id=uuid4()),
            amount=200.0,
        )
        mock_session.scalars.return_value.all.return_value = []

        result = await repository.update_transaction(params, user_id=TEST_USER_ID)

        assert result is None
        mock_session.commit.assert_not_called()

    async def test_update_ambiguous_match_raises(self, repository, mock_session):
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(
                match_text="almoço",
                date_local=date(2026, 6, 1),
            ),
            amount=200.0,
        )
        mock_session.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]

        with pytest.raises(AmbiguousTransactionError):
            await repository.update_transaction(params, user_id=TEST_USER_ID)
        mock_session.commit.assert_not_called()
