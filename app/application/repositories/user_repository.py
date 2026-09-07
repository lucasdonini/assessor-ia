from typing import Protocol
from uuid import UUID

from app.domain.model.user import User


class UserRepository(Protocol):
    async def create(self) -> User: ...

    async def list_users(self) -> list[User]: ...

    async def exists(self, user_id: UUID) -> bool: ...
