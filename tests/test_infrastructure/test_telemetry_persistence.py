import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.mongodb.repositories.telemetry_repository import (
    MongoTelemetryRepository,
)
from app.infrastructure.observability import TurnTelemetry, observe_block, observe_route
from app.services.monitor_service import MonitorService


def repository():
    result = AsyncMock()
    result.latest.return_value = ()
    return result


@pytest.mark.asyncio
async def test_restores_persistent_turns_without_resetting_current_uptime():
    repo = repository()
    first = TurnTelemetry(lambda _: MagicMock(), repo)
    await first.restore()
    async with first.persisted_turn("turn", "owner", "session"):
        observe_route("financial")
    saved = repo.save.await_args.args[0]
    assert saved.completed_at is not None
    assert saved.completed_at.tzinfo is not None
    repo.latest.return_value = (saved,)
    restarted = TurnTelemetry(lambda _: MagicMock(), repo)
    await restarted.restore()
    snapshot = MonitorService(restarted).snapshot()
    assert snapshot.retention == "mongo_window"
    assert snapshot.turns[0].turn_id == "turn"
    assert snapshot.service.in_progress == 0
    assert snapshot.persistence.history_loaded
    assert not snapshot.persistence.degraded
    assert snapshot.process_started_at >= first.snapshot().process_started_at
    await restarted.drain()


@pytest.mark.asyncio
async def test_immutable_save_uses_unique_turn_id_and_native_dates():
    repo = repository()
    store = TurnTelemetry(lambda _: MagicMock(), repo)
    async with store.persisted_turn("turn", "owner", "session"):
        observe_block("prompt_injection")
    turn = repo.save.await_args.args[0]
    database = MagicMock()
    collection = database.get_collection.return_value
    collection.update_one = AsyncMock()
    adapter = MongoTelemetryRepository(database)
    await adapter.save(turn)
    query, update = collection.update_one.await_args.args
    assert query == {"_id": "turn"}
    assert collection.update_one.await_args.kwargs == {"upsert": True}
    document = update["$setOnInsert"]
    assert isinstance(document["started_at"], datetime)
    assert isinstance(document["completed_at"], datetime)
    assert document["schema_version"] == 1
    assert "messages" not in document
    assert document["status"] == "blocked"
    assert database.get_collection.call_args.kwargs["write_concern"].document == {
        "j": True,
        "w": 1,
    }


@pytest.mark.asyncio
async def test_lost_ack_retry_is_bounded_and_failures_preserve_original_exception():
    repo = repository()
    store = TurnTelemetry(lambda _: MagicMock(), repo)
    await store.restore()
    repo.save.side_effect = [RuntimeError("lost ack"), None]
    async with store.persisted_turn("recovered", "owner", "session"):
        pass
    assert repo.save.await_count == 2
    assert store.snapshot().persistence.failed_writes == 0
    repo.save.side_effect = RuntimeError("PRIVATE_DATABASE_ERROR")
    with pytest.raises(ValueError, match="business error"):
        async with store.persisted_turn("failed", "owner", "session"):
            raise ValueError("business error")
    assert store.snapshot().turns[-1].status == "error"
    assert store.snapshot().persistence.failed_writes == 1
    assert store.snapshot().persistence.degraded
    assert "PRIVATE_DATABASE_ERROR" not in store.snapshot().model_dump_json()


@pytest.mark.asyncio
async def test_history_failure_does_not_stop_recording_and_write_timeout_is_visible(
    monkeypatch,
):
    repo = repository()
    repo.latest.side_effect = RuntimeError("unavailable")
    store = TurnTelemetry(lambda _: MagicMock(), repo)
    await store.restore()
    assert store.snapshot().persistence.degraded
    monkeypatch.setattr(
        "app.infrastructure.observability._PERSISTENCE_TIMEOUT_SECONDS", 0.01
    )

    async def blocked(turn):
        await asyncio.Event().wait()

    repo.save.side_effect = blocked
    async with store.persisted_turn("timeout", "owner", "session"):
        pass
    assert store.snapshot().persistence.failed_writes == 1
    assert store.snapshot().in_progress == 0
    assert len(store.snapshot().turns) == 1
    await store.drain()
    assert not store._pending


@pytest.mark.asyncio
async def test_cancellation_persists_closed_turn_and_drain_waits_for_shielded_write():
    repo = repository()
    started = asyncio.Event()
    writing = asyncio.Event()
    release = asyncio.Event()

    async def save(turn):
        writing.set()
        await release.wait()

    repo.save.side_effect = save
    store = TurnTelemetry(lambda _: MagicMock(), repo)

    async def graph():
        async with store.persisted_turn("cancelled", "owner", "session"):
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(graph())
    await started.wait()
    task.cancel()
    await writing.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert store.snapshot().persistence.pending_writes == 1
    drain = asyncio.create_task(store.drain())
    await asyncio.sleep(0)
    assert not drain.done()
    release.set()
    await drain
    assert store.snapshot().persistence.pending_writes == 0
    assert repo.save.await_args.args[0].status == "cancelled"
