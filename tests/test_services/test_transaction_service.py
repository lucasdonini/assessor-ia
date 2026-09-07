from datetime import date

import pytest

from app.application.exceptions import (
    NoTransactionChangesError,
    TransactionNotFoundError,
)
from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.domain.model.transaction import Category
from tests.user_identity import TEST_USER_ID

pytestmark = pytest.mark.asyncio


class TestCalculateTotalBalance:
    async def test_positive_balance(self, service, mock_repository):
        mock_repository.get_balance.return_value = 3000.0

        balance = await service.calculate_total_balance(user_id=TEST_USER_ID)

        assert balance == 3000.0
        mock_repository.get_balance.assert_called_once()

    async def test_negative_balance(self, service, mock_repository):
        mock_repository.get_balance.return_value = -2000.0

        balance = await service.calculate_total_balance(user_id=TEST_USER_ID)

        assert balance == -2000.0

    async def test_zero_balance(self, service, mock_repository):
        mock_repository.get_balance.return_value = 0.0

        balance = await service.calculate_total_balance(user_id=TEST_USER_ID)

        assert balance == 0.0

    async def test_calls_repository_once(self, service, mock_repository):
        mock_repository.get_balance.return_value = 0.0

        await service.calculate_total_balance(user_id=TEST_USER_ID)

        mock_repository.get_balance.assert_called_once()


class TestCalculateDailyBalance:
    async def test_daily_balance(self, service, mock_repository):
        mock_repository.get_balance.return_value = 300.0

        balance = await service.calculate_daily_balance(
            date(2026, 6, 1), user_id=TEST_USER_ID
        )

        assert balance == 300.0
        mock_repository.get_balance.assert_called_once_with(
            date(2026, 6, 1), user_id=TEST_USER_ID
        )

    async def test_daily_balance_negative(self, service, mock_repository):
        mock_repository.get_balance.return_value = -400.0

        balance = await service.calculate_daily_balance(
            date(2026, 6, 1), user_id=TEST_USER_ID
        )

        assert balance == -400.0


class TestSearchTransactions:
    async def test_search(self, service, mock_repository, sample_transactions_list):
        mock_repository.find.return_value = sample_transactions_list

        params = TransactionQueryParams(category=Category.FOOD)
        result = await service.search_transactions(params, user_id=TEST_USER_ID)

        assert result == sample_transactions_list
        mock_repository.find.assert_called_once_with(params, user_id=TEST_USER_ID)

    async def test_search_empty(self, service, mock_repository):
        mock_repository.find.return_value = []

        params = TransactionQueryParams(source_text="inexistente")
        result = await service.search_transactions(params, user_id=TEST_USER_ID)

        assert result == []

    async def test_search_passthrough_params(self, service, mock_repository):
        mock_repository.find.return_value = []
        params = TransactionQueryParams(limit=5)

        await service.search_transactions(params, user_id=TEST_USER_ID)

        mock_repository.find.assert_called_once_with(params, user_id=TEST_USER_ID)


class TestAddTransaction:
    async def test_add(
        self, service, mock_repository, sample_transaction, sample_transaction_with_id
    ):
        mock_repository.add_transaction.return_value = sample_transaction_with_id

        result = await service.add_transaction(sample_transaction, user_id=TEST_USER_ID)

        assert result == sample_transaction_with_id
        mock_repository.add_transaction.assert_called_once_with(
            sample_transaction, user_id=TEST_USER_ID
        )

    async def test_add_returns_from_repository(
        self, service, mock_repository, sample_transaction
    ):
        mock_repository.add_transaction.return_value = sample_transaction

        result = await service.add_transaction(sample_transaction, user_id=TEST_USER_ID)

        assert result == sample_transaction

    async def test_add_raises(self, service, mock_repository, sample_transaction):
        mock_repository.add_transaction.side_effect = Exception("fail")

        with pytest.raises(Exception):
            await service.add_transaction(sample_transaction, user_id=TEST_USER_ID)


class TestUpdateTransaction:
    async def test_update(
        self,
        service,
        mock_repository,
        sample_update_params_by_id,
        sample_transaction_with_id,
    ):
        mock_repository.update_transaction.return_value = sample_transaction_with_id

        result = await service.update_transaction(
            sample_update_params_by_id, user_id=TEST_USER_ID
        )

        assert result is not None
        mock_repository.update_transaction.assert_called_once_with(
            sample_update_params_by_id, user_id=TEST_USER_ID
        )

    async def test_update_nothing(
        self, service, mock_repository, sample_update_params_empty
    ):
        with pytest.raises(NoTransactionChangesError):
            await service.update_transaction(
                sample_update_params_empty, user_id=TEST_USER_ID
            )
        mock_repository.update_transaction.assert_not_called()

    async def test_update_not_found_raises(
        self, service, mock_repository, sample_update_params_by_id
    ):
        mock_repository.update_transaction.return_value = None

        with pytest.raises(TransactionNotFoundError):
            await service.update_transaction(
                sample_update_params_by_id, user_id=TEST_USER_ID
            )

    async def test_update_raises(
        self, service, mock_repository, sample_update_params_by_id
    ):
        mock_repository.update_transaction.side_effect = ValueError("no reference")

        with pytest.raises(ValueError):
            await service.update_transaction(
                sample_update_params_by_id, user_id=TEST_USER_ID
            )
