from typing import Protocol
from uuid import UUID


class ProfilePreferencesIndex(Protocol):
    async def upsert(self, preferences: str, *, user_id: UUID) -> None: ...

    async def search(self, query: str, *, user_id: UUID) -> list[str]: ...
