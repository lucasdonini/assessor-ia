from uuid import UUID

from app.application.ports.clock import Clock
from app.application.ports.logger import Logger
from app.application.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from app.domain.model.chat_entry import (
    ChatEntry,
    ChatError,
    ChatMessage,
)
from app.domain.model.chat_session import ChatSession

from .session_summary_service import SessionSummaryService


class ChatSessionService:
    def __init__(
        self,
        service: SessionSummaryService,
        repository: ChatSessionRepository,
        logger: Logger,
        clock: Clock,
    ) -> None:
        self._service = service
        self._repository = repository
        self._logger = logger
        self._clock = clock

    async def get_or_create_session(
        self, session_id: str, *, user_id: UUID
    ) -> ChatSession:
        now = self._clock.now()
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            started_at=now,
            updated_at=now,
        )

        return await self._repository.get_or_create(session)

    async def _save_entry(
        self, session_id: str, entry: ChatEntry, *, user_id: UUID
    ) -> None:
        now = self._clock.now()
        await self._repository.append_entry(
            session_id=session_id,
            user_id=user_id,
            entry=entry,
            updated_at=now,
        )

    async def save_message(
        self, session_id: str, message: ChatMessage, *, user_id: UUID
    ) -> None:
        await self._save_entry(session_id, message, user_id=user_id)
        self._logger.debug(
            "Message saved",
            details={
                "role": message.role.value,
                "content_length": len(message.content),
            },
        )

    async def save_error(
        self, session_id: str, error: Exception, *, user_id: UUID
    ) -> None:
        try:
            name = type(error).__name__
            summary = await self._service.summarize_exception(error)
            entry = ChatError(exception=name, summary=summary)
            await self._save_entry(session_id, entry, user_id=user_id)
            self._logger.debug(
                "Error saved",
                details={"exception_type": entry.exception},
            )
        except Exception as persistence_error:
            self._logger.exception(
                "Failed to save chat error",
                exception=persistence_error,
                details={"original_exception_type": type(error).__name__},
            )

    async def finalize_session(self, session_id: str, *, user_id: UUID) -> str | None:
        """
        Finalizes the active session:
            1. Fetch session from MongoDB
            2. If the session is not found or has no entries, returns None
            3. If the session is already finalized (has summary), returns the summary
            4. Summarize the entries and update the session in MongoDB
            5. Returns the generated summary
        """

        session = await self._repository.find_by_session_id(session_id, user_id=user_id)
        if not session or not session.entries:
            return None

        if session.summary and (summary := session.summary.strip()):
            return summary

        summary = await self._service.summarize_session(session.entries)
        await self._repository.update_summary(
            session_id=session_id,
            user_id=user_id,
            summary=summary,
            updated_at=self._clock.now(),
        )

        self._logger.debug(
            "Session finalized",
            details={"entry_count": len(session.entries)},
        )

        return summary
