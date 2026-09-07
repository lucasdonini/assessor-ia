from uuid import UUID

from app.application.repositories.user_repository import UserRepository
from app.domain.model.user import User


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def create(self) -> User:
        return await self._repository.create()

    async def list_users(self) -> list[User]:
        return await self._repository.list_users()

    async def exists(self, user_id: UUID) -> bool:
        return await self._repository.exists(user_id)
