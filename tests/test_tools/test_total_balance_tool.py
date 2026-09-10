from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.agents._core.schemas.tool_response import (
    ToolFailure,
    ToolSuccess,
)
from app.infrastructure.agents.tools.total_balance import TotalBalanceTool
from app.services.transaction_service import TransactionService

pytestmark = pytest.mark.asyncio


class TestTotalBalanceTool:
    @pytest.fixture
    def tool(self, mock_logger_factory: MagicMock):
        service = TransactionService.__new__(TransactionService)
        object.__setattr__(service, "_repository", None)
        return TotalBalanceTool(service=service, logger_factory=mock_logger_factory)

    async def test_returns_balance(self, tool):
        tool.service.calculate_total_balance = AsyncMock(return_value=5000.0)

        result = await tool._arun()

        assert isinstance(result, ToolSuccess)
        assert result.data.balance == 5000.0

    async def test_returns_zero(self, tool):
        tool.service.calculate_total_balance = AsyncMock(return_value=0.0)

        result = await tool._arun()

        assert isinstance(result, ToolSuccess)
        assert result.data.balance == 0.0

    async def test_returns_negative(self, tool):
        tool.service.calculate_total_balance = AsyncMock(return_value=-500.0)

        result = await tool._arun()

        assert isinstance(result, ToolSuccess)
        assert result.data.balance == -500.0

    async def test_handles_exception(self, tool):
        tool.service.calculate_total_balance = AsyncMock(
            side_effect=Exception("DB error")
        )

        result = await tool._arun()

        assert isinstance(result, ToolFailure)
        assert result.code == "unexpected_error"
        assert result.details == {}
