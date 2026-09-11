from uuid import UUID

from app.application.ports.logger import Logger, LoggerFactory
from app.application.ports.session_history_index import SessionHistoryIndex
from app.application.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from app.domain.model.chat_entry import ChatEntry
from app.domain.model.chat_session import ChatSessionSummarized


class ChatHistoryService:
    def __init__(
        self,
        repository: ChatSessionRepository,
        logger_factory: LoggerFactory,
        history_index: SessionHistoryIndex,
    ) -> None:
        self._repository = repository
        self._logger: Logger = logger_factory(__name__)
        self._history_index = history_index

    async def fetch_history(
        self, search: str = "", limit: int = 3, *, user_id: UUID
    ) -> list[ChatSessionSummarized]:
        """Find concluded sessions by relevance. Blank searches do no I/O."""
        search = search.strip()
        if not search:
            return []
        if limit <= 0:
            raise ValueError("History result limit must be positive")
        self._logger.debug(
            "Fetching history",
            details={"search_length": len(search), "limit": limit},
        )

        return await self._history_index.search(
            search=search, limit=limit, user_id=user_id
        )

    async def fetch_entries(
        self, session_id: str, *, user_id: UUID
    ) -> tuple[ChatEntry, ...]:
        self._logger.debug(
            "Fetching entries",
            details={"session_id": session_id[:8]},
        )
        session = await self._repository.find_by_session_id(session_id, user_id=user_id)
        entries = session.entries if session else tuple()

        self._logger.debug(
            "Entries fetched",
            details={"count": len(entries)},
        )
        return entries
