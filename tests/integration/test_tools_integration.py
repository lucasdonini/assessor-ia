from datetime import date

import pytest

from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.domain.model.transaction import Category, TransactionType
from app.infrastructure.agents._core.schemas.tool_response import (
    ToolFailure,
    ToolSuccess,
)
from app.infrastructure.agents.financial.schemas.transaction import (
    TransactionInput,
    TransactionOutput,
)
from app.infrastructure.agents.tools.add_transaction import AddTransactionTool
from app.infrastructure.agents.tools.daily_balance import DailyBalanceTool
from app.infrastructure.agents.tools.delete_transaction import (
    DeleteTransactionTool,
)
from app.infrastructure.agents.tools.restore_transaction import (
    RestoreTransactionTool,
)
from app.infrastructure.agents.tools.search_transaction import (
    SearchTransactionsTool,
)
from app.infrastructure.agents.tools.total_balance import TotalBalanceTool
from app.infrastructure.agents.tools.update_transaction import (
    UpdateTransactionTool,
)
from tests.user_identity import TEST_USER_ID

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("apply_migrations"),
]


@pytest.fixture
def total_balance_tool(transaction_service, mock_logger_factory):
    return TotalBalanceTool(
        service=transaction_service, logger_factory=mock_logger_factory
    )


@pytest.fixture
def daily_balance_tool(transaction_service, mock_logger_factory):
    return DailyBalanceTool(
        service=transaction_service, logger_factory=mock_logger_factory
    )


@pytest.fixture
def search_tool(transaction_service, mock_logger_factory):
    return SearchTransactionsTool(
        service=transaction_service, logger_factory=mock_logger_factory
    )


@pytest.fixture
def add_tool(transaction_service, mock_logger_factory):
    return AddTransactionTool(
        service=transaction_service, logger_factory=mock_logger_factory
    )


@pytest.fixture
def update_tool(transaction_service, mock_logger_factory):
    return UpdateTransactionTool(
        service=transaction_service, logger_factory=mock_logger_factory
    )


@pytest.fixture
def delete_tool(transaction_service, mock_logger_factory):
    return DeleteTransactionTool(
        service=transaction_service, logger_factory=mock_logger_factory
    )


@pytest.fixture
def restore_tool(transaction_service, mock_logger_factory):
    return RestoreTransactionTool(
        service=transaction_service, logger_factory=mock_logger_factory
    )


class TestTotalBalanceTool:
    async def test_returns_balance(self, total_balance_tool, seed_transactions):
        result = await total_balance_tool._arun()
        assert isinstance(result, ToolSuccess)
        assert result.data.balance == 7600.00

    async def test_empty_db_returns_zero(self, total_balance_tool, db_session):
        result = await total_balance_tool._arun()
        assert isinstance(result, ToolSuccess)
        assert result.data.balance == 0.0


class TestDailyBalanceTool:
    async def test_returns_daily_balance(self, daily_balance_tool, seed_transactions):
        result = await daily_balance_tool._arun(target_date=date(2026, 6, 1))
        assert isinstance(result, ToolSuccess)
        assert result.data.balance == 4850.00

    async def test_no_transactions_on_date(self, daily_balance_tool, db_session):
        result = await daily_balance_tool._arun(target_date=date(2025, 1, 1))
        assert isinstance(result, ToolSuccess)
        assert result.data.balance == 0.0


class TestSearchTransactionsTool:
    async def test_search_by_category(self, search_tool, seed_transactions):
        params = TransactionQueryParams(category=Category.FOOD, limit=50)
        result = await search_tool._arun(params=params)
        assert isinstance(result, ToolSuccess)
        assert len(result.data.transactions) >= 1

    async def test_no_results(self, search_tool, seed_transactions):
        params = TransactionQueryParams(source_text="xyz_nonexistent", limit=50)
        result = await search_tool._arun(params=params)
        assert isinstance(result, ToolSuccess)
        assert result.data.transactions == []

    async def test_returns_typed_models(self, search_tool, seed_transactions):
        params = TransactionQueryParams(limit=1)
        result = await search_tool._arun(params=params)
        assert isinstance(result.data.transactions[0], TransactionOutput)


class TestAddTransactionTool:
    async def test_add_transaction(self, add_tool, db_session):
        t = TransactionInput(
            amount=99.00,
            category=Category.GIFTS,
            transaction_type=TransactionType.EXPENSE,
            description="Presente",
            source_text="Comprei presente",
        )
        result = await add_tool._arun(transaction=t)
        assert isinstance(result, ToolSuccess)
        assert result.data.transaction is not None

    async def test_add_and_verify(self, add_tool, transaction_service, db_session):
        t = TransactionInput(
            amount=50.00,
            source_text="teste add tool",
        )
        add_result = await add_tool._arun(transaction=t)
        assert isinstance(add_result, ToolSuccess)

        params = TransactionQueryParams(source_text="teste add tool", limit=50)
        search_result = await transaction_service.search_transactions(
            params, user_id=TEST_USER_ID
        )
        assert len(search_result) >= 1


class TestUpdateTransactionTool:
    async def test_update_by_id(self, update_tool, seed_transactions):
        target = seed_transactions[0]
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(id=target.id),
            amount=6000.00,
            description="Atualizado via tool",
        )
        result = await update_tool._arun(params=params)
        assert isinstance(result, ToolSuccess)
        assert result.data.updated is not None

    async def test_nothing_to_update(self, update_tool, seed_transactions):
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(
                match_text="almoço",
                date_local=date(2026, 6, 1),
            ),
        )
        result = await update_tool._arun(params=params)
        assert isinstance(result, ToolFailure)
        assert result.code == "no_transaction_changes"


class TestDeleteTransactionTool:
    async def test_delete_by_id(self, delete_tool, seed_transactions):
        target = seed_transactions[0]
        query = UpdateTransactionQuery(id=target.id)
        result = await delete_tool._arun(query=query)
        assert isinstance(result, ToolSuccess)
        assert result.data.deleted is True

    async def test_delete_not_found(self, delete_tool, seed_transactions):
        from uuid import uuid4

        query = UpdateTransactionQuery(id=uuid4())
        result = await delete_tool._arun(query=query)
        assert isinstance(result, ToolFailure)
        assert result.code == "transaction_not_found"


class TestRestoreTransactionTool:
    async def test_restore_by_id(self, restore_tool, seed_transactions):
        target = seed_transactions[0]
        query = UpdateTransactionQuery(id=target.id)
        result = await restore_tool._arun(query=query)
        assert isinstance(result, ToolSuccess)
        assert result.data.restored is True

    async def test_restore_not_found(self, restore_tool, seed_transactions):
        from uuid import uuid4

        query = UpdateTransactionQuery(id=uuid4())
        result = await restore_tool._arun(query=query)
        assert isinstance(result, ToolFailure)
        assert result.code == "transaction_not_found"

    async def test_delete_then_restore_cycle(
        self, restore_tool, delete_tool, seed_transactions
    ):
        target = seed_transactions[0]
        delete_query = UpdateTransactionQuery(id=target.id)
        delete_result = await delete_tool._arun(query=delete_query)
        assert isinstance(delete_result, ToolSuccess)
        assert delete_result.data.deleted is True

        restore_result = await restore_tool._arun(query=delete_query)
        assert isinstance(restore_result, ToolSuccess)
        assert restore_result.data.restored is True
