from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pymongo import AsyncMongoClient
from testcontainers.community.mongodb import MongoDbContainer

from app.infrastructure.mongodb.repositories.telemetry_repository import (
    MongoTelemetryRepository,
)
from app.infrastructure.observability import TurnTelemetry, observe_node, observe_route
from app.services.monitor_service import MonitorService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_real_mongo_keeps_all_turns_restores_latest_50_and_deduplicates():
    with MongoDbContainer("mongo:7") as container:
        client = AsyncMongoClient(container.get_connection_url())
        try:
            # Production injects a MongoManager whose connection is already initialized.
            await client.admin.command("ping")
            database = client.telemetry_persistence_test
            repository = MongoTelemetryRepository(database)
            store = TurnTelemetry(lambda _: MagicMock(), repository)
            await store.restore()
            ids = []
            for index in range(51):
                turn_id = str(uuid4())
                ids.append(turn_id)
                async with store.persisted_turn(turn_id, "owner", "session"):
                    with observe_node("financial"):
                        observe_route("financial")
            assert not store.snapshot().persistence.degraded
            last = store.snapshot().turns[-1]
            await repository.save(last)
            assert await database.telemetry_turns.count_documents({}) == 51
            expected = (
                await database.telemetry_turns.find({})
                .sort([("completed_at", -1), ("_id", -1)])
                .limit(50)
                .to_list(length=50)
            )
            restarted = TurnTelemetry(
                lambda _: MagicMock(), MongoTelemetryRepository(database)
            )
            await restarted.restore()
            snapshot = MonitorService(restarted).snapshot()
            assert snapshot.retention == "mongo_window"
            assert snapshot.window_turns == 50
            assert [turn.turn_id for turn in snapshot.turns] == [
                doc["_id"] for doc in expected
            ]
            assert snapshot.turns[0].started_at.tzinfo is not None
            assert snapshot.turns[0].nodes[0].node == "financial"
            indexes = await database.telemetry_turns.index_information()
            assert all("expireAfterSeconds" not in index for index in indexes.values())
            await store.drain()
            await restarted.drain()
        finally:
            await client.close()
