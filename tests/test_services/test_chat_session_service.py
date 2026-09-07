from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from app.application.ports.logger import Logger
from app.application.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from app.domain.model.chat_entry import AssistantMessage, ChatEntry, HumanMessage
from app.domain.model.chat_session import ChatSession
from app.infrastructure.clock import FixedClock
from app.services.chat_session_service import ChatSessionService
from tests.user_identity import TEST_USER_ID

_FIXED_TIME = datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc)
_SESSION_ID = "session-123"


def _session(
    *,
    entries: tuple[ChatEntry, ...] | None = None,
    summary: str | None = None,
) -> ChatSession:
    return ChatSession(
        session_id=_SESSION_ID,
        started_at=_FIXED_TIME,
        updated_at=_FIXED_TIME,
        summary=summary,
        entries=() if entries is None else entries,
        user_id=TEST_USER_ID,
    )


class TestChatSessionService:
    @pytest.fixture
    def summary_service(self):
        service = MagicMock()
        service.summarize_session = AsyncMock()
        service.summarize_exception = AsyncMock()
        return service

    @pytest.fixture
    def repository(self):
        return create_autospec(ChatSessionRepository, instance=True)

    @pytest.fixture
    def service(self, summary_service, repository):
        return ChatSessionService(
            service=summary_service,
            repository=repository,
            logger=MagicMock(spec=Logger),
            clock=FixedClock(_FIXED_TIME, "America/Sao_Paulo"),
        )

    @pytest.mark.asyncio
    async def test_get_or_create_session_delegates_candidate_to_repository(
        self, service, repository
    ):
        persisted_session = _session()
        repository.get_or_create.return_value = persisted_session

        result = await service.get_or_create_session(_SESSION_ID, user_id=TEST_USER_ID)

        assert result is persisted_session
        repository.get_or_create.assert_awaited_once_with(_session())

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "message",
        [
            HumanMessage(content="Olá"),
            AssistantMessage(content="Resposta"),
        ],
    )
    async def test_save_message_appends_entry(self, service, repository, message):
        await service.save_message(_SESSION_ID, message, user_id=TEST_USER_ID)

        repository.append_entry.assert_awaited_once_with(
            session_id=_SESSION_ID,
            entry=message,
            updated_at=_FIXED_TIME,
            user_id=TEST_USER_ID,
        )

    @pytest.mark.asyncio
    async def test_save_message_propagates_persistence_failure(
        self, service, repository
    ):
        repository.append_entry.side_effect = RuntimeError("MongoDB unavailable")

        with pytest.raises(RuntimeError, match="MongoDB unavailable"):
            await service.save_message(
                _SESSION_ID, HumanMessage(content="Olá"), user_id=TEST_USER_ID
            )

    @pytest.mark.asyncio
    async def test_save_error(self, service, summary_service, repository):
        summary_service.summarize_exception.return_value = "Ocorreu um erro interno."
        error = ValueError("Algo deu errado")

        await service.save_error(_SESSION_ID, error, user_id=TEST_USER_ID)

        repository.append_entry.assert_awaited_once()
        call = repository.append_entry.await_args
        saved_entry = call.kwargs["entry"]
        assert call.kwargs["session_id"] == _SESSION_ID
        assert call.kwargs["updated_at"] == _FIXED_TIME
        assert saved_entry.exception == "ValueError"
        assert saved_entry.summary == "Ocorreu um erro interno."
        summary_service.summarize_exception.assert_awaited_once_with(error)

    @pytest.mark.asyncio
    async def test_save_error_logs_secondary_failure_without_raising(
        self, service, summary_service
    ):
        original_error = ValueError("original")
        persistence_error = RuntimeError("summary unavailable")
        summary_service.summarize_exception.side_effect = persistence_error

        await service.save_error(_SESSION_ID, original_error, user_id=TEST_USER_ID)

        service._logger.exception.assert_called_once_with(
            "Failed to save chat error",
            exception=persistence_error,
            details={"original_exception_type": "ValueError"},
        )

    @pytest.mark.asyncio
    async def test_finalize_session_with_summary(
        self, service, summary_service, repository
    ):
        entries = (HumanMessage(content="Olá"),)
        repository.find_by_session_id.return_value = _session(entries=entries)
        summary_service.summarize_session.return_value = "Resumo da sessão"

        result = await service.finalize_session(_SESSION_ID, user_id=TEST_USER_ID)

        assert result == "Resumo da sessão"
        repository.find_by_session_id.assert_awaited_once_with(
            _SESSION_ID, user_id=TEST_USER_ID
        )
        summary_service.summarize_session.assert_awaited_once_with(entries)
        repository.update_summary.assert_awaited_once_with(
            session_id=_SESSION_ID,
            summary="Resumo da sessão",
            updated_at=_FIXED_TIME,
            user_id=TEST_USER_ID,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("session", [None, _session(entries=())])
    async def test_finalize_session_without_entries(
        self, service, summary_service, repository, session
    ):
        repository.find_by_session_id.return_value = session

        result = await service.finalize_session(_SESSION_ID, user_id=TEST_USER_ID)

        assert result is None
        summary_service.summarize_session.assert_not_awaited()
        repository.update_summary.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_finalize_session_already_summarized_is_idempotent(
        self, service, summary_service, repository
    ):
        repository.find_by_session_id.return_value = _session(
            entries=(HumanMessage(content="Olá"),),
            summary="Resumo existente",
        )

        result = await service.finalize_session(_SESSION_ID, user_id=TEST_USER_ID)

        assert result == "Resumo existente"
        repository.find_by_session_id.assert_awaited_once_with(
            _SESSION_ID, user_id=TEST_USER_ID
        )
        summary_service.summarize_session.assert_not_awaited()
        repository.update_summary.assert_not_awaited()
