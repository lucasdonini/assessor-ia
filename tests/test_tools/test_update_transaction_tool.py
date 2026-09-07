from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.exceptions import NoTransactionChangesError
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.domain.model.transaction import Category, Transaction, TransactionType
from app.infrastructure.agents.financial.schemas.tool_response import (
    ToolFailure,
    ToolSuccess,
)
from app.infrastructure.agents.tools.update_transaction import (
    UpdateTransactionTool,
)
from app.services.transaction_service import TransactionService
from tests.user_identity import TEST_USER_ID

pytestmark = pytest.mark.asyncio


class TestUpdateTransactionTool:
    @pytest.fixture
    def tool(self, mock_logger_factory: MagicMock):
        service = TransactionService.__new__(TransactionService)
        object.__setattr__(service, "_repository", None)
        return UpdateTransactionTool(
            service=service, logger_factory=mock_logger_factory
        )

    async def test_updates_and_returns_ok(self, tool):
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(id=uuid4()),
            amount=200.0,
            category=Category.FOOD,
        )
        updated = Transaction(
            amount=200.0,
            category=Category.FOOD,
            transaction_type=TransactionType.EXPENSE,
            source_text="original",
            user_id=TEST_USER_ID,
        )
        tool.service.update_transaction = AsyncMock(return_value=updated)

        result = await tool._arun(params)

        assert isinstance(result, ToolSuccess)
        assert result.data.updated is not None
        assert result.data.updated.amount == 200.0

    async def test_nothing_to_update(self, tool):
        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(
                match_text="teste", date_local=date(2026, 1, 1)
            ),
        )
        tool.service.update_transaction = AsyncMock(
            side_effect=NoTransactionChangesError
        )

        result = await tool._arun(params)

        assert isinstance(result, ToolFailure)
        assert result.code == "no_transaction_changes"

    async def test_handles_exception(self, tool):
        tool.service.update_transaction = AsyncMock(side_effect=Exception("fail"))

        params = UpdateTransactionParams(
            query=UpdateTransactionQuery(id=uuid4()),
            amount=200.0,
        )
        result = await tool._arun(params)

        assert isinstance(result, ToolFailure)
        assert result.code == "unexpected_error"
        assert result.details == {}
