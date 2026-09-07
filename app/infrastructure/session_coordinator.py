import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field


@dataclass
class _SessionLock:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


class SessionCoordinator:
    """Serialize a session within one event loop, including its waiting requests."""

    def __init__(self) -> None:
        self._locks: dict[str, _SessionLock] = {}

    @asynccontextmanager
    async def hold(self, session_id: str) -> AsyncIterator[None]:
        entry = self._locks.setdefault(session_id, _SessionLock())
        entry.users += 1
        try:
            async with entry.lock:
                yield
        finally:
            entry.users -= 1
            if entry.users == 0:
                del self._locks[session_id]
