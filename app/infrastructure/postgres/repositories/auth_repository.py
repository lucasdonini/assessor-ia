from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.postgres.entities.google_identity import (
    GoogleGrantORM,
    GoogleIdentityORM,
)
from app.infrastructure.postgres.entities.user import UserORM


class SQLAlchemyAuthRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def resolve_identity(self, subject: str) -> UUID:
        async with self._factory.begin() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": "google-identity:" + subject},
            )
            identity = await session.get(GoogleIdentityORM, subject)
            if identity is not None:
                return identity.user_id
            user = UserORM()
            session.add(user)
            await session.flush()
            session.add(GoogleIdentityORM(subject=subject, user_id=user.id))
            return user.id

    async def save_grant(self, user_id: UUID, email: str, ciphertext: str) -> None:
        async with self._factory.begin() as session:
            statement = insert(GoogleGrantORM).values(
                user_id=user_id, email=email, ciphertext=ciphertext
            )
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[GoogleGrantORM.user_id],
                    set_={"email": email, "ciphertext": ciphertext},
                )
            )

    async def get_grant(self, user_id: UUID) -> tuple[str, str] | None:
        async with self._factory() as session:
            row = await session.scalar(
                select(GoogleGrantORM).where(GoogleGrantORM.user_id == user_id)
            )
            return (row.email, row.ciphertext) if row else None

    async def delete_grant(self, user_id: UUID) -> None:
        async with self._factory.begin() as session:
            await session.execute(
                delete(GoogleGrantORM).where(GoogleGrantORM.user_id == user_id)
            )
