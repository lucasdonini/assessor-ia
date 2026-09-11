from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import MagicMock, create_autospec

import pytest

from app.application.ports.session_history_index import SessionHistoryIndex
from app.domain.model.chat_session import ChatSessionSummarized
from app.infrastructure.vectorstore.ingestors.history_ingestor import HistoryIngestor
from tests.user_identity import TEST_USER_ID


async def summaries() -> AsyncIterator[ChatSessionSummarized]:
    session = ChatSessionSummarized(
        user_id=TEST_USER_ID,
        session_id="s",
        summary="Resumo",
        started_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    yield replace(session, summary="  ")
    yield session
    yield replace(session, session_id="s2")


@pytest.mark.asyncio
async def test_backfill_streams_nonempty_summaries() -> None:
    index = create_autospec(SessionHistoryIndex, instance=True)
    ingestor = HistoryIngestor(
        history_index=index, logger_factory=lambda _: MagicMock()
    )
    assert await ingestor.ingest(summaries()) == 2
    assert index.index.await_count == 2


@pytest.mark.asyncio
async def test_backfill_stops_on_failure_and_can_be_repeated() -> None:
    index = create_autospec(SessionHistoryIndex, instance=True)
    index.index.side_effect = RuntimeError("offline")
    ingestor = HistoryIngestor(
        history_index=index, logger_factory=lambda _: MagicMock()
    )
    with pytest.raises(RuntimeError):
        await ingestor.ingest(summaries())
    assert index.index.await_count == 1
    index.index.side_effect = None
    assert await ingestor.ingest(summaries()) == 2
