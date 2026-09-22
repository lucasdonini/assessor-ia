"""Local MCP entry point for the financial agent's existing tools."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any, AsyncIterator
from uuid import UUID

from dishka import AsyncContainer
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from app.application.models.transaction_query import TransactionQueryParams
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.application.models.user_context import UserContext
from app.application.ports.logger import LoggerFactory
from app.bootstrap import create_container
from app.infrastructure.agents._core.schemas.tool_response import ToolFailure
from app.infrastructure.agents._core.user_context import bind_user_context
from app.infrastructure.agents.financial.schemas.transaction import TransactionInput
from app.infrastructure.agents.tools.add_transaction import AddTransactionTool
from app.infrastructure.agents.tools.consult_profile import ConsultProfileTool
from app.infrastructure.agents.tools.daily_balance import DailyBalanceTool
from app.infrastructure.agents.tools.delete_transaction import DeleteTransactionTool
from app.infrastructure.agents.tools.restore_transaction import RestoreTransactionTool
from app.infrastructure.agents.tools.search_history import SearchHistoryTool
from app.infrastructure.agents.tools.search_transaction import SearchTransactionsTool
from app.infrastructure.agents.tools.total_balance import TotalBalanceTool
from app.infrastructure.agents.tools.update_transaction import UpdateTransactionTool
from app.services.chat_history_service import ChatHistoryService
from app.services.transaction_service import TransactionService
from app.services.user_profile_service import UserProfileService
from app.services.user_service import UserService

READ_ONLY = ToolAnnotations(read_only_hint=True)
WRITES_DATA = ToolAnnotations(read_only_hint=False, destructive_hint=False)


@dataclass(slots=True)
class Runtime:
    user: UserContext
    tools: dict[str, Any]


_runtime: Runtime | None = None


def _configured_user() -> UserContext:
    raw_id = os.environ.get("ASSESSOR_MCP_USER_ID", "")
    try:
        return UserContext(user_id=UUID(raw_id))
    except ValueError as exc:
        raise RuntimeError("ASSESSOR_MCP_USER_ID must be a valid user UUID") from exc


@asynccontextmanager
async def lifespan(_: MCPServer[Any]) -> AsyncIterator[None]:
    global _runtime
    user = _configured_user()
    container: AsyncContainer = create_container()
    try:
        if not await (await container.get(UserService)).exists(user.user_id):
            raise RuntimeError(
                "ASSESSOR_MCP_USER_ID does not identify an existing user"
            )
        logger_factory = await container.get(LoggerFactory)
        transaction_service = await container.get(TransactionService)
        profile_service = await container.get(UserProfileService)
        history_service = await container.get(ChatHistoryService)
        _runtime = Runtime(
            user=user,
            tools={
                "total_balance": TotalBalanceTool(
                    service=transaction_service, logger_factory=logger_factory
                ),
                "daily_balance": DailyBalanceTool(
                    service=transaction_service, logger_factory=logger_factory
                ),
                "search_transactions": SearchTransactionsTool(
                    service=transaction_service, logger_factory=logger_factory
                ),
                "add_transaction": AddTransactionTool(
                    service=transaction_service, logger_factory=logger_factory
                ),
                "update_transaction": UpdateTransactionTool(
                    service=transaction_service, logger_factory=logger_factory
                ),
                "delete_transaction": DeleteTransactionTool(
                    service=transaction_service, logger_factory=logger_factory
                ),
                "restore_transaction": RestoreTransactionTool(
                    service=transaction_service, logger_factory=logger_factory
                ),
                "consult_profile": ConsultProfileTool(
                    service=profile_service, logger_factory=logger_factory
                ),
                "search_history": SearchHistoryTool(
                    service=history_service, logger_factory=logger_factory
                ),
            },
        )
        yield
    finally:
        _runtime = None
        await container.close()


mcp = MCPServer(
    name="assessor-financeiro",
    version="1.0.0",
    instructions=(
        "Financial tools for the locally configured Assessor user. "
        "Reads access private financial data; writes change it. "
        "Confirm add, update, delete, and restore operations with the user."
    ),
    lifespan=lifespan,
)


async def _call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    runtime = _runtime
    if runtime is None:
        raise RuntimeError("MCP server is not initialized")
    with bind_user_context(runtime.user):
        result: BaseModel = await runtime.tools[name].ainvoke(arguments)
    if isinstance(result, ToolFailure):
        logging.getLogger(__name__).warning("MCP tool failed: %s", result.code)
    return result.model_dump(mode="json")


@mcp.tool(name="total_balance", title="Total balance", annotations=READ_ONLY)
async def total_balance() -> dict[str, Any]:
    """Get the current balance of the configured user's full transaction history."""
    return await _call("total_balance", {})


@mcp.tool(name="daily_balance", title="Daily balance", annotations=READ_ONLY)
async def daily_balance(target_date: date) -> dict[str, Any]:
    """Get the accumulated balance through a local calendar date (YYYY-MM-DD)."""
    return await _call("daily_balance", {"target_date": target_date})


@mcp.tool(
    name="search_transactions", title="Search transactions", annotations=READ_ONLY
)
async def search_transactions(params: TransactionQueryParams) -> dict[str, Any]:
    """Find transactions by text, category, type, or date; default limit is 50."""
    return await _call("search_transactions", {"params": params.model_dump()})


@mcp.tool(name="add_transaction", title="Add transaction", annotations=WRITES_DATA)
async def add_transaction(transaction: TransactionInput) -> dict[str, Any]:
    """Record a transaction for the configured user. Requires user confirmation."""
    return await _call("add_transaction", {"transaction": transaction.model_dump()})


@mcp.tool(
    name="update_transaction", title="Update transaction", annotations=WRITES_DATA
)
async def update_transaction(params: UpdateTransactionParams) -> dict[str, Any]:
    """Update a transaction by ID or text and local date. Requires confirmation."""
    return await _call("update_transaction", {"params": params.model_dump()})


@mcp.tool(
    name="delete_transaction", title="Cancel transaction", annotations=WRITES_DATA
)
async def delete_transaction(query: UpdateTransactionQuery) -> dict[str, Any]:
    """Soft-delete a transaction by ID or text and date. Requires confirmation."""
    return await _call("delete_transaction", {"query": query.model_dump()})


@mcp.tool(
    name="restore_transaction", title="Restore transaction", annotations=WRITES_DATA
)
async def restore_transaction(query: UpdateTransactionQuery) -> dict[str, Any]:
    """Restore a canceled transaction. Requires user confirmation."""
    return await _call("restore_transaction", {"query": query.model_dump()})


@mcp.tool(
    name="consult_profile", title="Consult financial profile", annotations=READ_ONLY
)
async def consult_profile(query: str = Field(min_length=1)) -> dict[str, Any]:
    """Read the user's financial profile and relevant preferences for a question."""
    return await _call("consult_profile", {"query": query})


@mcp.tool(
    name="search_history", title="Search previous conversations", annotations=READ_ONLY
)
async def search_history(search: str = Field(min_length=1)) -> dict[str, Any]:
    """Search summaries of the configured user's previous conversations."""
    return await _call("search_history", {"search": search})


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    mcp.run(transport="stdio")
