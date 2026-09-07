from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from beanie import Document, Indexed
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.domain.model.chat_entry import ChatMessageRole


class ChatMessageDocument(BaseModel):
    content: str
    role: ChatMessageRole
    type: Literal["message"] = "message"


class ChatErrorDocument(BaseModel):
    exception: str
    summary: str
    type: Literal["error"] = "error"


ChatEntryDocument = Annotated[
    ChatMessageDocument | ChatErrorDocument, Field(discriminator="type")
]


class ChatSessionDocument(Document):
    """ORM for mongodb collection"""

    user_id: UUID
    session_id: Annotated[str, Indexed(unique=True)]
    started_at: Annotated[datetime, Indexed()]
    updated_at: datetime | None = None
    summary: str | None = None
    entries: list[ChatEntryDocument]

    class Settings:
        name = "sessions"
        indexes = [IndexModel([("user_id", ASCENDING), ("updated_at", DESCENDING)])]


class ChatSessionSummaryProjection(BaseModel):
    """Beanie projection"""

    user_id: UUID
    session_id: str
    summary: str | None
    started_at: datetime
