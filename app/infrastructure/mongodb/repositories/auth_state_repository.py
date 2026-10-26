from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.application.models.google_identity import OAuthTransaction, WebSession


class MongoAuthStateRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database["auth_state"]

    async def initialize(self) -> None:
        await self._collection.create_index("expires_at", expireAfterSeconds=0)

    async def put_oauth(self, key: str, transaction: OAuthTransaction) -> None:
        value = transaction.model_dump(mode="json")
        value["verifier"] = transaction.verifier.get_secret_value()
        await self._put("oauth:" + key, value, 600)

    async def pop_oauth(self, key: str) -> OAuthTransaction | None:
        row = await self._collection.find_one_and_delete(
            {"_id": "oauth:" + key, "expires_at": {"$gt": datetime.now(UTC)}}
        )
        return OAuthTransaction.model_validate(row["value"]) if row else None

    async def put_session(self, key: str, session: WebSession) -> None:
        await self._put("session:" + key, session.model_dump(mode="json"), 86400)

    async def get_session(self, key: str) -> WebSession | None:
        row = await self._collection.find_one(
            {"_id": "session:" + key, "expires_at": {"$gt": datetime.now(UTC)}}
        )
        return WebSession.model_validate(row["value"]) if row else None

    async def delete_session(self, key: str) -> None:
        await self._collection.delete_one({"_id": "session:" + key})

    async def _put(self, key: str, value: dict[str, Any], ttl: int) -> None:
        await self._collection.insert_one(
            {
                "_id": key,
                "value": value,
                "expires_at": datetime.now(UTC) + timedelta(seconds=ttl),
            }
        )
