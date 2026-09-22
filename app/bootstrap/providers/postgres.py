from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide

from app.application.repositories.transaction_repository import TransactionRepository
from app.application.repositories.user_repository import UserRepository
from app.infrastructure.config import PostgresConfig
from app.infrastructure.postgres.pg_connection import PostgresManager
from app.infrastructure.postgres.repositories.transaction_repository import (
    SQLAlchemyTransactionRepository,
)
from app.infrastructure.postgres.repositories.user_repository import (
    SQLAlchemyUserRepository,
)


class PostgresProvider(Provider):
    scope = Scope.APP

    @provide
    async def postgres_manager(
        self, config: PostgresConfig
    ) -> AsyncIterable[PostgresManager]:
        manager = PostgresManager(config.url)
        try:
            yield manager
        finally:
            await manager.dispose()

    @provide
    def user_repository(self, manager: PostgresManager) -> UserRepository:
        return SQLAlchemyUserRepository(manager.session_factory)

    @provide
    def transaction_repository(self, manager: PostgresManager) -> TransactionRepository:
        return SQLAlchemyTransactionRepository(manager.session_factory)
