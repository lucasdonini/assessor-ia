from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from qdrant_client import QdrantClient

from app.infrastructure.vectorstore.repositories.profile_preferences_index import (
    QDrantProfilePreferencesIndex,
)


@pytest.mark.asyncio
async def test_semantic_query_is_user_scoped_and_upsert_replaces_old_text() -> None:
    client = QdrantClient(":memory:")
    embeddings = MagicMock()
    embeddings.generate_batch.return_value = [[1.0, 0.0]]
    embeddings.generate.return_value = [0.9, 0.1]
    index = QDrantProfilePreferencesIndex(
        client=client, embeddings=embeddings, dimensions=2
    )
    try:
        await index.initialize()
        user, other = uuid4(), uuid4()
        assert await index.search("crypto", user_id=user) == []
        await index.upsert("No aggressive investments", user_id=user)
        await index.upsert("Other user's private preferences", user_id=other)
        assert await index.search("crypto", user_id=user) == [
            "No aggressive investments"
        ]
        await index.upsert("Prefer liquidity", user_id=user)
        assert await index.search("crypto", user_id=user) == ["Prefer liquidity"]
        assert client.count("profile_preferences").count == 2
        embeddings.generate.assert_called_with("crypto")
    finally:
        client.close()
