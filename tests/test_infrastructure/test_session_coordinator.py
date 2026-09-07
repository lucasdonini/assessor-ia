import asyncio

import pytest

from app.infrastructure.session_coordinator import SessionCoordinator


@pytest.mark.asyncio
async def test_waiter_cancellation_preserves_lock_and_other_sessions_progress():
    coordinator = SessionCoordinator()
    entered = asyncio.Event()

    async def waiter():
        async with coordinator.hold("same"):
            entered.set()

    async with coordinator.hold("same"):
        first = asyncio.create_task(waiter())
        second = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        async with coordinator.hold("different"):
            assert not entered.is_set()
        assert not entered.is_set()
    await second
    assert entered.is_set()
    assert not coordinator._locks
