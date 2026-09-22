from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.application.models.user_context import UserContext
from app.infrastructure.agents._core.schemas.tool_response import (
    ToolFailure,
    ToolSuccess,
)
from app.infrastructure.agents._core.user_context import get_user_context
from app.infrastructure.agents.tools.total_balance import TotalBalanceResponse
from app.mcp_server import Runtime, _call, _configured_user, mcp


@pytest.mark.asyncio
async def test_catalog_exposes_all_financial_agent_tools() -> None:
    catalog = {tool.name: tool for tool in await mcp.list_tools()}

    assert set(catalog) == {
        "total_balance",
        "daily_balance",
        "search_transactions",
        "add_transaction",
        "update_transaction",
        "delete_transaction",
        "restore_transaction",
        "consult_profile",
        "search_history",
    }
    for name, tool in catalog.items():
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is (
            name
            not in {
                "add_transaction",
                "update_transaction",
                "delete_transaction",
                "restore_transaction",
            }
        )
        assert "user_id" not in str(tool.input_schema)


def test_identity_requires_configured_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASSESSOR_MCP_USER_ID", raising=False)
    with pytest.raises(RuntimeError, match="ASSESSOR_MCP_USER_ID"):
        _configured_user()

    monkeypatch.setenv("ASSESSOR_MCP_USER_ID", "invalid")
    with pytest.raises(RuntimeError, match="valid user UUID"):
        _configured_user()


@pytest.mark.asyncio
async def test_dispatch_binds_user_and_serializes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000123")
    previous_user_id = get_user_context().user_id

    async def invoke(_: dict[str, object]) -> ToolSuccess[TotalBalanceResponse]:
        assert get_user_context().user_id == user_id
        return ToolSuccess(data=TotalBalanceResponse(balance=42.0))

    tool = AsyncMock()
    tool.ainvoke.side_effect = invoke
    monkeypatch.setattr(
        "app.mcp_server._runtime",
        Runtime(user=UserContext(user_id=user_id), tools={"total_balance": tool}),
    )

    assert await _call("total_balance", {}) == {
        "status": "ok",
        "data": {"balance": 42.0},
    }
    assert get_user_context().user_id == previous_user_id


@pytest.mark.asyncio
async def test_dispatch_returns_public_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = AsyncMock()
    tool.ainvoke.return_value = ToolFailure.unexpected_error()
    monkeypatch.setattr(
        "app.mcp_server._runtime",
        Runtime(
            user=UserContext(user_id=UUID("00000000-0000-0000-0000-000000000123")),
            tools={"total_balance": tool},
        ),
    )

    result = await _call("total_balance", {})
    assert result["code"] == "unexpected_error"
    assert "traceback" not in str(result).lower()
