from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from app.application.ports.logger import Logger
from app.application.ports.session_history_index import SessionHistoryIndex
from app.application.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from app.domain.model.chat_entry import AssistantMessage, ChatEntry, HumanMessage
from app.domain.model.chat_session import ChatSession, ChatSessionSummarized
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
            logger_factory=lambda _: MagicMock(spec=Logger),
            clock=FixedClock(_FIXED_TIME, "America/Sao_Paulo"),
            history_index=create_autospec(SessionHistoryIndex, instance=True),
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
        service._history_index.index.assert_awaited_once()
        assert (
            service._history_index.index.await_args.args[0].summary
            == "Resumo existente"
        )

    @pytest.mark.asyncio
    async def test_index_failure_preserves_summary_and_retry_reuses_it(
        self,
        service: ChatSessionService,
        summary_service: MagicMock,
        repository: MagicMock,
    ) -> None:
        session = _session(entries=(HumanMessage(content="viagem"),))
        repository.find_by_session_id.return_value = session
        summary_service.summarize_session.return_value = "Resumo persistido"

        async def fail_after_save(indexed: ChatSessionSummarized) -> None:
            repository.update_summary.assert_awaited_once()
            assert indexed.user_id == TEST_USER_ID
            raise RuntimeError("Qdrant unavailable")

        service._history_index.index.side_effect = fail_after_save
        assert (
            await service.finalize_session(_SESSION_ID, user_id=TEST_USER_ID)
            == "Resumo persistido"
        )
        repository.find_by_session_id.return_value = _session(
            entries=session.entries, summary="Resumo persistido"
        )
        service._history_index.index.side_effect = None
        assert (
            await service.finalize_session(_SESSION_ID, user_id=TEST_USER_ID)
            == "Resumo persistido"
        )
        summary_service.summarize_session.assert_awaited_once()
        repository.update_summary.assert_awaited_once()
        assert service._history_index.index.await_count == 2

    @pytest.mark.asyncio
    async def test_mongo_failure_prevents_indexing(
        self,
        service: ChatSessionService,
        summary_service: MagicMock,
        repository: MagicMock,
    ) -> None:
        repository.find_by_session_id.return_value = _session(
            entries=(HumanMessage(content="oi"),)
        )
        summary_service.summarize_session.return_value = "Resumo"
        repository.update_summary.side_effect = RuntimeError("Mongo unavailable")
        with pytest.raises(RuntimeError):
            await service.finalize_session(_SESSION_ID, user_id=TEST_USER_ID)
        service._history_index.index.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_generated_summary_is_not_saved_or_indexed(
        self,
        service: ChatSessionService,
        summary_service: MagicMock,
        repository: MagicMock,
    ) -> None:
        repository.find_by_session_id.return_value = _session(
            entries=(HumanMessage(content="oi"),)
        )
        summary_service.summarize_session.return_value = "  "
        with pytest.raises(ValueError):
            await service.finalize_session(_SESSION_ID, user_id=TEST_USER_ID)
        repository.update_summary.assert_not_awaited()
        service._history_index.index.assert_not_awaited()
