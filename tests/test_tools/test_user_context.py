import asyncio
from contextvars import Context
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.agents._core.schemas.tool_response import ToolFailure
from app.infrastructure.agents.tools.total_balance import TotalBalanceTool
from app.services.transaction_service import TransactionService


@pytest.mark.asyncio
async def test_missing_server_context_never_calls_financial_service():
    service = MagicMock(spec=TransactionService)
    service.calculate_total_balance = AsyncMock()
    tool = TotalBalanceTool(service=service, logger_factory=lambda _: MagicMock())
    assert "user_id" not in tool.tool_call_schema.model_json_schema()["properties"]
    result = await asyncio.create_task(tool.ainvoke({}), context=Context())
    assert isinstance(result, ToolFailure)
    service.calculate_total_balance.assert_not_awaited()
