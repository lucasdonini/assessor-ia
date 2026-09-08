from typing import Protocol
from uuid import UUID

from app.domain.model.user_profile import UserProfile


class UserProfileRepository(Protocol):
    async def upsert(self, profile: UserProfile) -> None: ...

    async def find_by_user_id(self, user_id: UUID) -> UserProfile | None: ...
