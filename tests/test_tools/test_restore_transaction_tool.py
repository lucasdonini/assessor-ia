from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.exceptions import TransactionNotFoundError
from app.application.models.transaction_update import (
    UpdateTransactionQuery,
)
from app.domain.model.transaction import Category, Transaction, TransactionType
from app.infrastructure.agents.financial.schemas.tool_response import (
    ToolFailure,
    ToolSuccess,
)
from app.infrastructure.agents.tools.restore_transaction import (
    RestoreTransactionTool,
)
from app.services.transaction_service import TransactionService
from tests.user_identity import TEST_USER_ID

pytestmark = pytest.mark.asyncio


class TestRestoreTransactionTool:
    @pytest.fixture
    def tool(self, mock_logger_factory: MagicMock):
        service = TransactionService.__new__(TransactionService)
        object.__setattr__(service, "_repository", None)
        return RestoreTransactionTool(
            service=service, logger_factory=mock_logger_factory
        )

    async def test_restores_by_id_returns_true(self, tool):
        query = UpdateTransactionQuery(id=uuid4())
        updated = Transaction(
            amount=100.00,
            category=Category.OTHER,
            transaction_type=TransactionType.EXPENSE,
            source_text="restaurado",
            user_id=TEST_USER_ID,
        )
        tool.service.update_transaction = AsyncMock(return_value=updated)

        result = await tool._arun(query)

        assert isinstance(result, ToolSuccess)
        assert result.data.restored is True

    async def test_no_transaction_found_returns_false(self, tool):
        query = UpdateTransactionQuery(
            match_text="inexistente",
            date_local=date(2026, 1, 1),
        )
        tool.service.update_transaction = AsyncMock(
            side_effect=TransactionNotFoundError
        )

        result = await tool._arun(query)

        assert isinstance(result, ToolFailure)
        assert result.code == "transaction_not_found"

    async def test_handles_exception(self, tool):
        tool.service.update_transaction = AsyncMock(side_effect=Exception("DB error"))

        query = UpdateTransactionQuery(id=uuid4())
        result = await tool._arun(query)

        assert isinstance(result, ToolFailure)
        assert result.code == "unexpected_error"
        assert result.details == {}
