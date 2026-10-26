from datetime import UTC
from typing import Any

from bson.codec_options import CodecOptions
from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.write_concern import WriteConcern

from app.application.models.observability import TurnObservation


class MongoTelemetryRepository:
    """One immutable, journal-acknowledged document per completed graph turn."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.get_collection(
            "telemetry_turns",
            write_concern=WriteConcern(w=1, j=True),
            codec_options=CodecOptions(tz_aware=True, tzinfo=UTC),
        )

    async def initialize(self) -> None:
        await self._collection.create_index(
            [("completed_at", DESCENDING), ("_id", DESCENDING)],
            name="telemetry_recent_turns",
        )

    async def save(self, turn: TurnObservation) -> None:
        # The unique _id plus setOnInsert makes retries safe after lost acknowledgments.
        document = turn.model_dump(mode="json")
        document["started_at"] = turn.started_at
        document["completed_at"] = turn.completed_at or turn.started_at
        document["schema_version"] = 1
        await self._collection.update_one(
            {"_id": turn.turn_id}, {"$setOnInsert": document}, upsert=True
        )

    async def latest(self, limit: int) -> tuple[TurnObservation, ...]:
        if limit <= 0:
            return ()
        cursor = (
            self._collection.find({})
            .sort([("completed_at", DESCENDING), ("_id", DESCENDING)])
            .limit(limit)
        )
        documents = await cursor.to_list(length=limit)
        turns = [TurnObservation.model_validate(document) for document in documents]
        return tuple(reversed(turns))
