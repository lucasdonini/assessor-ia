from datetime import datetime, timezone
from unittest.mock import MagicMock, create_autospec

import pytest

from app.application.ports.logger import Logger
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
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("search", ["", "transporte"])
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
        repository.find_summaries.return_value = summaries

        result = await service.fetch_history(search=search, user_id=TEST_USER_ID)

        assert result == summaries
        repository.find_summaries.assert_awaited_once_with(
            search=search, limit=3, user_id=TEST_USER_ID
        )

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
