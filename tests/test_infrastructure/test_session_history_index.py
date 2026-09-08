from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from qdrant_client import QdrantClient, models

from app.application.exceptions import SessionHistoryIndexError
from app.domain.model.chat_session import ChatSessionSummarized
from app.infrastructure.vectorstore.repositories.session_history_index import (
    QDrantSessionHistoryIndex,
)
from tests.user_identity import TEST_USER_ID


def summary() -> ChatSessionSummarized:
    return ChatSessionSummarized(
        user_id=TEST_USER_ID,
        session_id="session-not-a-uuid",
        summary="Viagem para João Pessoa em agosto",
        started_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def make_index(
    client: QdrantClient | MagicMock, embeddings: MagicMock
) -> QDrantSessionHistoryIndex:
    return QDrantSessionHistoryIndex(
        client=client,
        embeddings=embeddings,
        collection_name="session-history",
        dimensions=3,
        logger=MagicMock(),
        score_threshold=0.6,
    )


@pytest.mark.asyncio
async def test_real_local_qdrant_filter_threshold_and_idempotency() -> None:
    """Exercise actual Qdrant search with deterministic fake embeddings."""
    with closing(QdrantClient(":memory:")) as client:
        client.create_collection(
            "session-history",
            vectors_config={
                "": models.VectorParams(size=3, distance=models.Distance.COSINE)
            },
        )
        embeddings = MagicMock()
        embeddings.generate_batch.return_value = [[1.0, 0.0, 0.0]]
        embeddings.generate.return_value = [0.9, 0.1, 0.0]
        index = make_index(client, embeddings)
        own = summary()
        await index.index(own)
        await index.index(own)
        await index.index(replace(own, user_id=uuid4(), summary="Outra pessoa"))
        embeddings.generate_batch.return_value = [[0.0, 0.0, 1.0]]
        await index.index(
            replace(own, session_id="unrelated", summary="Curso de inglês")
        )
        assert client.count("session-history").count == 3
        assert await index.search(
            "destino das férias", user_id=TEST_USER_ID, limit=3
        ) == [own]
        assert await index.search("destino", user_id=uuid4(), limit=3) == []
        embeddings.generate.return_value = [-1.0, 0.0, 0.0]
        assert await index.search("irrelevante", user_id=TEST_USER_ID, limit=3) == []


@pytest.mark.asyncio
async def test_blank_inputs_do_not_call_external_dependencies() -> None:
    client, embeddings = MagicMock(), MagicMock()
    index = make_index(client, embeddings)
    assert await index.search(" \t", user_id=TEST_USER_ID, limit=3) == []
    await index.index(replace(summary(), summary="  "))
    assert client.mock_calls == embeddings.mock_calls == []


@pytest.mark.asyncio
async def test_invalid_embedding_is_rejected_before_write() -> None:
    client, embeddings = MagicMock(), MagicMock()
    embeddings.generate_batch.return_value = [[1.0, 0.0]]
    with pytest.raises(SessionHistoryIndexError):
        await make_index(client, embeddings).index(summary())
    client.upsert.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("named", [False, True])
async def test_validation_accepts_default_vector_and_existing_keyword_index(
    named: bool,
) -> None:
    client = MagicMock()
    vector = models.VectorParams(size=3, distance=models.Distance.COSINE)
    client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(vectors={"": vector} if named else vector)
        ),
        payload_schema={
            "user_id": SimpleNamespace(data_type=models.PayloadSchemaType.KEYWORD)
        },
    )
    await make_index(client, MagicMock()).validate_collection()
    client.create_collection.assert_not_called()
    client.create_payload_index.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("problem", ["size", "metric", "named", "index", "unavailable"])
async def test_validation_rejects_incompatible_collection(problem: str) -> None:
    client = MagicMock()
    vector = models.VectorParams(
        size=5 if problem == "size" else 3,
        distance=models.Distance.DOT if problem == "metric" else models.Distance.COSINE,
    )
    client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors={"other": vector} if problem == "named" else vector
            )
        ),
        payload_schema={}
        if problem == "index"
        else {"user_id": SimpleNamespace(data_type="keyword")},
    )
    if problem == "unavailable":
        client.get_collection.side_effect = RuntimeError("unavailable")
    with pytest.raises(SessionHistoryIndexError):
        await make_index(client, MagicMock()).validate_collection()


@pytest.mark.asyncio
async def test_bad_payload_and_foreign_owner_are_not_returned() -> None:
    client, embeddings = MagicMock(), MagicMock()
    embeddings.generate.return_value = [1.0, 0.0, 0.0]
    valid = {
        "user_id": str(TEST_USER_ID),
        "session_id": "s",
        "summary": "Resumo",
        "started_at": "2026-08-01T00:00:00Z",
    }
    client.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(payload=None),
            SimpleNamespace(payload={**valid, "started_at": "invalid"}),
            SimpleNamespace(payload={**valid, "user_id": str(uuid4())}),
            SimpleNamespace(payload=valid),
        ]
    )
    result = await make_index(client, embeddings).search(
        "assunto", user_id=TEST_USER_ID, limit=3
    )
    assert len(result) == 1
    assert result[0].started_at == datetime(2026, 8, 1, tzinfo=timezone.utc)
    call = client.query_points.call_args.kwargs
    assert call["query_filter"].must[0].match.value == str(TEST_USER_ID)
    assert call["score_threshold"] == 0.6


@pytest.mark.asyncio
async def test_search_failure_is_not_an_empty_result() -> None:
    client, embeddings = MagicMock(), MagicMock()
    embeddings.generate.side_effect = RuntimeError("provider unavailable")
    with pytest.raises(SessionHistoryIndexError):
        await make_index(client, embeddings).search(
            "assunto", user_id=TEST_USER_ID, limit=3
        )
