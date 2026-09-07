import re
from datetime import datetime
from typing import Mapping
from uuid import UUID

from beanie import UpdateResponse
from beanie.operators import In, NotIn, Push, RegEx, Set, SetOnInsert
from pymongo import DESCENDING
from pymongo.results import UpdateResult

from app.domain.exception.chat_session import (
    ChatSessionAlreadyFinalizedException,
    ChatSessionNotFoundException,
    ChatSessionWriteConflictException,
)
from app.domain.model.chat_entry import ChatEntry
from app.domain.model.chat_session import ChatSession, ChatSessionSummarized
from app.infrastructure.mongodb.entities.chat_session import (
    ChatSessionDocument,
    ChatSessionSummaryProjection,
)
from app.infrastructure.mongodb.mappers.chat_session_mapper import (
    ChatSessionMapper,
    ChatSessionSummarizedMapper,
)


class BeanieChatSessionRepository:
    async def get_or_create(self, session: ChatSession) -> ChatSession:
        document = await ChatSessionDocument.find_one(
            ChatSessionDocument.session_id == session.session_id
        ).update(
            SetOnInsert(
                {
                    ChatSessionDocument.session_id: session.session_id,
                    ChatSessionDocument.user_id: session.user_id,
                    ChatSessionDocument.updated_at: session.updated_at,
                    ChatSessionDocument.started_at: session.started_at,
                    ChatSessionDocument.summary: session.summary,
                    ChatSessionDocument.entries: [
                        ChatSessionMapper.model_entry_to_document(entry)
                        for entry in session.entries
                    ],
                }
            ),
            response_type=UpdateResponse.NEW_DOCUMENT,
            upsert=True,
        )
        assert isinstance(document, ChatSessionDocument)
        if document.user_id != session.user_id:
            raise ChatSessionNotFoundException(session.session_id)
        return ChatSessionMapper.document_to_model(document)

    async def append_entry(
        self,
        session_id: str,
        entry: ChatEntry,
        updated_at: datetime,
        *,
        is_retry: bool = False,
        user_id: UUID,
    ) -> None:
        document_entry = ChatSessionMapper.model_entry_to_document(entry)
        result = await ChatSessionDocument.find_one(
            ChatSessionDocument.user_id == user_id,
            ChatSessionDocument.session_id == session_id,
            In(ChatSessionDocument.summary, [None, ""]),
        ).update(
            Push({ChatSessionDocument.entries: document_entry}),
            Set({ChatSessionDocument.updated_at: updated_at}),
            response_type=UpdateResponse.UPDATE_RESULT,
        )

        if not isinstance(result, UpdateResult):
            raise TypeError(
                "The result of the update was not of the expected type. "
                f"Received: {type(result).__name__!r}. "
                f"Expected: {UpdateResult.__name__!r}."
            )

        if result.matched_count == 1:
            return

        session = await ChatSessionDocument.find_one(
            ChatSessionDocument.user_id == user_id,
            ChatSessionDocument.session_id == session_id,
        )
        if not session:
            raise ChatSessionNotFoundException(session_id)
        if session.summary and session.summary.strip():
            raise ChatSessionAlreadyFinalizedException(session_id)

        # Because of concurrency, if the session's state
        # was updated during the function execution
        # the filter might fail in the first update
        # and succeed in the second, so we try again once
        if is_retry:
            raise ChatSessionWriteConflictException(session_id)
        await self.append_entry(
            session_id=session_id,
            entry=entry,
            updated_at=updated_at,
            is_retry=True,
            user_id=user_id,
        )

    async def find_by_session_id(
        self, session_id: str, *, user_id: UUID
    ) -> ChatSession | None:
        document = await ChatSessionDocument.find_one(
            ChatSessionDocument.user_id == user_id,
            ChatSessionDocument.session_id == session_id,
        )
        if document is None:
            return None
        return ChatSessionMapper.document_to_model(document)

    async def update_summary(
        self, session_id: str, summary: str, updated_at: datetime, *, user_id: UUID
    ) -> None:
        await ChatSessionDocument.find_one(
            ChatSessionDocument.user_id == user_id,
            ChatSessionDocument.session_id == session_id,
        ).update(
            Set(
                {
                    ChatSessionDocument.updated_at: updated_at,
                    ChatSessionDocument.summary: summary,
                }
            )
        )

    async def find_summaries(
        self, search: str = "", limit: int = 3, *, user_id: UUID
    ) -> list[ChatSessionSummarized]:
        find_filter: list[Mapping] = [
            {"user_id": user_id},
            NotIn(ChatSessionDocument.summary, [None, ""]),
        ]
        if search:
            pattern = re.compile(pattern=search, flags=re.IGNORECASE)
            find_filter.append(RegEx(ChatSessionDocument.summary, pattern=pattern))

        documents = await (
            ChatSessionDocument.find(*find_filter)
            .project(ChatSessionSummaryProjection)
            .sort(ChatSessionDocument.updated_at, DESCENDING)  # type: ignore[arg-type]
            .limit(limit)
            .to_list()
        )
        return [
            ChatSessionSummarizedMapper.document_to_model(document)
            for document in documents
        ]
