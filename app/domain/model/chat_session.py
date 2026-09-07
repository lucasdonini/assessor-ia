from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .chat_entry import ChatEntry


@dataclass(slots=True, frozen=True)
class ChatSession:
    user_id: UUID
    session_id: str
    started_at: datetime
    updated_at: datetime | None = None
    summary: str | None = None
    entries: tuple[ChatEntry, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class ChatSessionSummarized:
    user_id: UUID
    session_id: str
    summary: str | None
    started_at: datetime
