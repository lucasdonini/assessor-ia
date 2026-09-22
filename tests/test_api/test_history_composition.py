from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from app.application.exceptions import SessionHistoryIndexError
from app.bootstrap.providers import qdrant
from app.infrastructure.vectorstore.config import SessionHistoryConfig
from app.lifespan import lifespan


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [False, True])
async def test_provider_validates_history_before_providing_it(
    monkeypatch: pytest.MonkeyPatch, invalid: bool
) -> None:
    index = AsyncMock()
    if invalid:
        index.validate_collection.side_effect = SessionHistoryIndexError()
    index_factory = MagicMock(return_value=index)
    monkeypatch.setattr(qdrant, "QDrantSessionHistoryIndex", index_factory)

    dependency = qdrant.build_history_index(
        client=MagicMock(),
        embeddings=MagicMock(),
        config=SessionHistoryConfig("session-history", 768),
        logger_factory=MagicMock(),
    )
    if invalid:
        with pytest.raises(SessionHistoryIndexError):
            await dependency
    else:
        assert await dependency is index
    index.validate_collection.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_resolves_roots_and_closes_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    faq_ingestor = MagicMock()
    container = AsyncMock()
    container.get.side_effect = [MagicMock(), faq_ingestor]
    app = FastAPI()
    app.state.dishka_container = container
    monkeypatch.setattr("app.lifespan.setup_logger", MagicMock())
    monkeypatch.setattr("app.lifespan.settings", MagicMock())

    async with lifespan(app):
        faq_ingestor.ingest.assert_called_once_with()

    assert container.get.await_count == 2
    container.close.assert_awaited_once_with()
