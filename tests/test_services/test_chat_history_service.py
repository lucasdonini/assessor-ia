from datetime import datetime, timezone
from unittest.mock import MagicMock, create_autospec

import pytest

from app.application.ports.logger import Logger
from app.application.ports.session_history_index import SessionHistoryIndex
from app.application.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from app.domain.model.chat_entry import AssistantMessage, HumanMessage
from app.domain.model.chat_session import ChatSession, ChatSessionSummarized
from app.services.chat_history_service import ChatHistoryService
from tests.user_identity import TEST_USER_ID


class TestChatHistoryService:
    @pytest.fixture
    def repository(self):
        return create_autospec(ChatSessionRepository, instance=True)

    @pytest.fixture
    def service(self, repository):
        return ChatHistoryService(
            repository=repository,
            logger=MagicMock(spec=Logger),
            history_index=create_autospec(SessionHistoryIndex, instance=True),
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("search", ["transporte", "  transporte  "])
    async def test_fetch_history(self, service, repository, search):
        fixed = datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc)
        summaries = [
            ChatSessionSummarized(
                session_id="session-123",
                summary="Resumo",
                started_at=fixed,
                user_id=TEST_USER_ID,
            )
        ]
        service._history_index.search.return_value = summaries

        result = await service.fetch_history(search=search, user_id=TEST_USER_ID)

        assert result == summaries
        service._history_index.search.assert_awaited_once_with(
            search=search.strip(), limit=3, user_id=TEST_USER_ID
        )
        repository.find_summaries.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("search", ["", "  ", "\n\t"])
    async def test_blank_search_does_no_io(
        self, service: ChatHistoryService, repository: MagicMock, search: str
    ) -> None:
        assert await service.fetch_history(search, user_id=TEST_USER_ID) == []
        service._history_index.search.assert_not_awaited()
        assert repository.mock_calls == []

    @pytest.mark.asyncio
    async def test_no_matches_has_no_recent_sessions_fallback(
        self, service: ChatHistoryService, repository: MagicMock
    ) -> None:
        service._history_index.search.return_value = []
        assert await service.fetch_history("curso", user_id=TEST_USER_ID) == []
        assert repository.mock_calls == []

    @pytest.mark.asyncio
    async def test_fetch_entries_found(self, service, repository):
        fixed = datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc)
        entries = (
            HumanMessage(content="Olá"),
            AssistantMessage(content="Oi!"),
        )
        repository.find_by_session_id.return_value = ChatSession(
            session_id="session-123",
            started_at=fixed,
            entries=entries,
            user_id=TEST_USER_ID,
        )

        result = await service.fetch_entries("session-123", user_id=TEST_USER_ID)

        assert result == entries

    @pytest.mark.asyncio
    async def test_fetch_entries_not_found(self, service, repository):
        repository.find_by_session_id.return_value = None

        result = await service.fetch_entries("nonexistent", user_id=TEST_USER_ID)

        assert result == ()
