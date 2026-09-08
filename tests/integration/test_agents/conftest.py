from collections.abc import Generator
from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

from app.application.ports.faq_search import FaqSearch
from app.application.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from app.infrastructure.agents import build_agent_graph
from app.infrastructure.agents._core.factories.langchain_agent_factory import (
    LangChainAgentFactory,
)
from app.infrastructure.agents.financial import FinancialAgentNode
from app.infrastructure.agents.financial.financial_agent import FinancialAgentTools
from app.infrastructure.agents.tools.add_transaction import AddTransactionTool
from app.infrastructure.agents.tools.daily_balance import DailyBalanceTool
from app.infrastructure.agents.tools.delete_transaction import DeleteTransactionTool
from app.infrastructure.agents.tools.restore_transaction import RestoreTransactionTool
from app.infrastructure.agents.tools.search_history import SearchHistoryTool
from app.infrastructure.agents.tools.search_transaction import SearchTransactionsTool
from app.infrastructure.agents.tools.total_balance import TotalBalanceTool
from app.infrastructure.agents.tools.update_transaction import UpdateTransactionTool
from app.infrastructure.clock import FixedClock
from app.infrastructure.llms import fast_llm, llm_gemini
from app.infrastructure.text_generator import LLMTextGenerator
from app.services.chat_history_service import ChatHistoryService


@pytest.fixture
def application_clock() -> FixedClock:
    return FixedClock(
        datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc),
        "America/Sao_Paulo",
    )


def _make_aimessage(content: str = "", tool_calls: list | None = None):
    from langchain_core.messages import AIMessage

    return AIMessage(content=content, tool_calls=tool_calls or [])


def tool_call_dict(name: str, args: dict, call_id: str | None = None) -> dict:
    return {
        "name": name,
        "args": args,
        "id": call_id or f"call_{name}",
    }


@pytest.fixture
def mock_gemini_ainvoke() -> Generator[AsyncMock, None, None]:
    with patch(
        "langchain_google_genai.chat_models.ChatGoogleGenerativeAI.ainvoke",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@pytest.fixture
def mock_groq_ainvoke() -> Generator[AsyncMock, None, None]:
    with patch(
        "langchain_groq.chat_models.ChatGroq.ainvoke",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@pytest.fixture
def mock_all_llms(
    mock_gemini_ainvoke: AsyncMock,
    mock_groq_ainvoke: AsyncMock,
) -> dict[str, AsyncMock]:
    return {
        "gemini": mock_gemini_ainvoke,
        "groq": mock_groq_ainvoke,
    }


@pytest.fixture
def chat_history_service(mock_logger) -> ChatHistoryService:
    repository = create_autospec(ChatSessionRepository, instance=True)
    repository.find_summaries.return_value = []
    return ChatHistoryService(
        repository=repository,
        logger=mock_logger,
        history_index=AsyncMock(search=AsyncMock(return_value=[])),
    )


@pytest.fixture
def financial_agent_node(
    transaction_service, application_clock, chat_history_service, mock_logger_factory
) -> FinancialAgentNode:
    tools: FinancialAgentTools = {
        "total_balance": TotalBalanceTool(
            service=transaction_service, logger_factory=mock_logger_factory
        ),
        "daily_balance": DailyBalanceTool(
            service=transaction_service, logger_factory=mock_logger_factory
        ),
        "search_transactions": SearchTransactionsTool(
            service=transaction_service, logger_factory=mock_logger_factory
        ),
        "add_transaction": AddTransactionTool(
            service=transaction_service, logger_factory=mock_logger_factory
        ),
        "update_transaction": UpdateTransactionTool(
            service=transaction_service, logger_factory=mock_logger_factory
        ),
        "delete_transaction": DeleteTransactionTool(
            service=transaction_service, logger_factory=mock_logger_factory
        ),
        "restore_transaction": RestoreTransactionTool(
            service=transaction_service, logger_factory=mock_logger_factory
        ),
        "search_history": SearchHistoryTool(
            service=chat_history_service, logger_factory=mock_logger_factory
        ),
    }
    return FinancialAgentNode(
        agent_factory=LangChainAgentFactory(llm=llm_gemini),
        tools=tools,
        logger_factory=mock_logger_factory,
        clock=application_clock,
    )


@pytest.fixture
def agent_graph(
    transaction_service, application_clock, chat_history_service, mock_logger_factory
):
    return build_agent_graph(
        transaction_service=transaction_service,
        chat_history_service=chat_history_service,
        faq_search=MagicMock(spec=FaqSearch),
        text_generator=LLMTextGenerator(fast_llm),
        logger_factory=mock_logger_factory,
        trace_context_factory=lambda _: nullcontext(),
        interaction_incrementer=lambda: 1,
        clock=application_clock,
    )
