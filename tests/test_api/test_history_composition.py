from importlib import import_module
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from app.api.dependencies import get_chat_session_service, get_history_index
from app.application.exceptions import SessionHistoryIndexError


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [False, True])
async def test_lifespan_validates_history_before_using_it(
    monkeypatch: pytest.MonkeyPatch, invalid: bool
) -> None:
    module = import_module("app.lifespan")
    index = AsyncMock()
    if invalid:
        index.validate_collection.side_effect = SessionHistoryIndexError()
    index_factory = MagicMock(return_value=index)
    monkeypatch.setattr(module, "QDrantSessionHistoryIndex", index_factory)
    monkeypatch.setattr(
        module, "QDrantProfilePreferencesIndex", MagicMock(return_value=AsyncMock())
    )
    monkeypatch.setattr(module, "setup_logger", MagicMock())
    monkeypatch.setattr(module, "settings", MagicMock())
    monkeypatch.setattr(module, "create_logger", MagicMock())
    faq = MagicMock()
    monkeypatch.setattr(module, "QDrantFaqIngestor", faq)
    monkeypatch.setattr(module, "MongoManager", MagicMock(return_value=AsyncMock()))
    postgres = MagicMock(dispose=AsyncMock())
    monkeypatch.setattr(module, "PostgresManager", MagicMock(return_value=postgres))
    for name in (
        "SQLAlchemyUserRepository",
        "SQLAlchemyTransactionRepository",
        "BeanieChatSessionRepository",
        "LLMTextGenerator",
        "TransactionService",
        "SystemClock",
        "QDrantFaqSearch",
        "build_agent_graph",
    ):
        monkeypatch.setattr(module, name, MagicMock())
    history_service = MagicMock()
    monkeypatch.setattr(module, "ChatHistoryService", history_service)
    app = FastAPI()
    if invalid:
        with pytest.raises(SessionHistoryIndexError):
            async with module.lifespan(app):
                pytest.fail("Startup should fail on invalid history configuration")
        faq.assert_not_called()
        history_service.assert_not_called()
    else:
        async with module.lifespan(app):
            assert app.state.history_index is index
            assert history_service.call_args.kwargs["history_index"] is index
            request = Request({"type": "http", "app": app})
            service = get_chat_session_service(
                history_index=get_history_index(request),
                clock=MagicMock(),
                logger_factory=MagicMock(),
                session_repository=MagicMock(),
                session_summary_service=MagicMock(),
            )
            assert service._history_index is index
        postgres.dispose.assert_awaited_once()
    index.validate_collection.assert_awaited_once()
