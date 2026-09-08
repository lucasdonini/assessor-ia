from typing import Protocol
from uuid import UUID

from app.domain.model.chat_session import ChatSessionSummarized


class SessionHistoryIndex(Protocol):
    async def index(self, session: ChatSessionSummarized) -> None: ...

    async def search(
        self, search: str, *, user_id: UUID, limit: int
    ) -> list[ChatSessionSummarized]: ...
