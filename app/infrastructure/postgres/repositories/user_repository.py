from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.model.user import User
from app.infrastructure.postgres.entities.user import UserORM


class SQLAlchemyUserRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self) -> User:
        async with self._session_factory() as session:
            user = UserORM()
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return User(id=user.id, created_at=user.created_at)

    async def list_users(self) -> list[User]:
        async with self._session_factory() as session:
            users = await session.scalars(
                select(UserORM).order_by(UserORM.created_at, UserORM.id)
            )
            return [User(id=user.id, created_at=user.created_at) for user in users]

    async def exists(self, user_id: UUID) -> bool:
        async with self._session_factory() as session:
            return await session.get(UserORM, user_id) is not None
