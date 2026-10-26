import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from pymongo import AsyncMongoClient
from testcontainers.community.mongodb import MongoDbContainer

from app.application.models.google_identity import OAuthTransaction, WebSession
from app.infrastructure.mongodb.repositories.auth_state_repository import (
    MongoAuthStateRepository,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_oauth_state_atomic_consumption_expiry_and_session_invalidation():
    with MongoDbContainer("mongo:7") as container:
        client = AsyncMongoClient(container.get_connection_url())
        try:
            repository = MongoAuthStateRepository(client.auth_tests)
            await repository.initialize()
            transaction = OAuthTransaction(
                nonce="nonce", verifier=SecretStr("pkce-secret"), purpose="login"
            )
            await repository.put_oauth("hash", transaction)
            consumed = await asyncio.gather(
                repository.pop_oauth("hash"), repository.pop_oauth("hash")
            )
            assert sum(item is not None for item in consumed) == 1
            restored = next(item for item in consumed if item is not None)
            assert restored.verifier.get_secret_value() == "pkce-secret"
            await repository.put_oauth("expired", transaction)
            await client.auth_tests.auth_state.update_one(
                {"_id": "oauth:expired"},
                {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}},
            )
            assert await repository.pop_oauth("expired") is None
            session = WebSession(
                user_id=uuid4(),
                subject="subject",
                email="synthetic@example.com",
                csrf="csrf",
            )
            await repository.put_session("session-hash", session)
            assert await repository.get_session("session-hash") == session
            await repository.delete_session("session-hash")
            assert await repository.get_session("session-hash") is None
        finally:
            await client.close()
