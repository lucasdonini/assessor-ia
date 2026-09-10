from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.domain.model.transaction import Category, Transaction, TransactionType
from app.infrastructure.agents._core.schemas.tool_response import (
    ToolFailure,
    ToolSuccess,
)
from app.infrastructure.agents.financial.schemas.transaction import TransactionOutput
from app.infrastructure.agents.tools.search_transaction import (
    SearchTransactionsTool,
)
from app.services.transaction_service import TransactionService
from tests.user_identity import TEST_USER_ID

pytestmark = pytest.mark.asyncio


class TestSearchTransactionsTool:
    @pytest.fixture
    def tool(self, mock_logger_factory: MagicMock):
        service = TransactionService.__new__(TransactionService)
        object.__setattr__(service, "_repository", None)
        return SearchTransactionsTool(
            service=service, logger_factory=mock_logger_factory
        )

    async def test_returns_transactions(self, tool):
        mock_result = [
            Transaction(
                amount=100.0,
                category=Category.FOOD,
                transaction_type=TransactionType.EXPENSE,
                source_text="test",
                user_id=TEST_USER_ID,
            )
        ]
        tool.service.search_transactions = AsyncMock(return_value=mock_result)

        params = TransactionQueryParams(category=Category.FOOD)
        result = await tool._arun(params)

        assert isinstance(result, ToolSuccess)
        assert len(result.data.transactions) == 1

    async def test_returns_empty_list(self, tool):
        tool.service.search_transactions = AsyncMock(return_value=[])

        params = TransactionQueryParams()
        result = await tool._arun(params)

        assert isinstance(result, ToolSuccess)
        assert result.data.transactions == []

    async def test_handles_exception(self, tool):
        tool.service.search_transactions = AsyncMock(side_effect=Exception("fail"))

        params = TransactionQueryParams()
        result = await tool._arun(params)

        assert isinstance(result, ToolFailure)

    async def test_transactions_are_typed_model(self, tool):
        mock_result = [
            Transaction(
                amount=50.0,
                category=Category.OTHER,
                transaction_type=TransactionType.EXPENSE,
                source_text="source",
                user_id=TEST_USER_ID,
            )
        ]
        tool.service.search_transactions = AsyncMock(return_value=mock_result)

        params = TransactionQueryParams()
        result = await tool._arun(params)

        assert isinstance(result, ToolSuccess)
        assert isinstance(result.data.transactions[0], TransactionOutput)
