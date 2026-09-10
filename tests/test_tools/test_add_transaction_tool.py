from unittest.mock import AsyncMock, MagicMock

import pytest

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
from app.services.transaction_service import TransactionService

pytestmark = pytest.mark.asyncio


class TestAddTransactionTool:
    @pytest.fixture
    def tool(self, mock_logger_factory: MagicMock):
        service = TransactionService.__new__(TransactionService)
        object.__setattr__(service, "_repository", None)
        return AddTransactionTool(service=service, logger_factory=mock_logger_factory)

    async def test_adds_and_returns_ok(self, tool):
        t = TransactionInput(
            amount=100.0,
            category=Category.FOOD,
            transaction_type=TransactionType.EXPENSE,
            source_text="test",
        )
        tool.service.add_transaction = AsyncMock(
            side_effect=lambda transaction, *, user_id: transaction
        )

        result = await tool._arun(transaction=t)

        assert isinstance(result, ToolSuccess)
        assert result.data.transaction is not None
        assert result.data.transaction.amount == 100.0
        assert isinstance(result.data.transaction, TransactionOutput)

    async def test_handles_exception(self, tool):
        tool.service.add_transaction = AsyncMock(side_effect=Exception("fail"))

        t = TransactionInput(
            amount=100.0,
            source_text="test",
        )
        result = await tool._arun(transaction=t)

        assert isinstance(result, ToolFailure)
