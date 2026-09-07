from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.model.chat_entry import ChatEntry
from app.domain.model.chat_session import ChatSession, ChatSessionSummarized


class ChatSessionRepository(Protocol):
    async def get_or_create(self, session: ChatSession) -> ChatSession: ...

    async def append_entry(
        self, session_id: str, entry: ChatEntry, updated_at: datetime, *, user_id: UUID
    ) -> None: ...

    async def find_by_session_id(
        self, session_id: str, *, user_id: UUID
    ) -> ChatSession | None: ...

    async def update_summary(
        self, session_id: str, summary: str, updated_at: datetime, *, user_id: UUID
    ) -> None: ...

    async def find_summaries(
        self, search: str = "", limit: int = 3, *, user_id: UUID
    ) -> list[ChatSessionSummarized]: ...
