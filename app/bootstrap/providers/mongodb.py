from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide

from app.application.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from app.application.repositories.user_profile_repository import UserProfileRepository
from app.infrastructure.config import MongoConfig
from app.infrastructure.mongodb.client import MongoManager
from app.infrastructure.mongodb.repositories.chat_session_repository import (
    BeanieChatSessionRepository,
)
from app.infrastructure.mongodb.repositories.user_profile_repository import (
    BeanieUserProfileRepository,
)


class MongoProvider(Provider):
    scope = Scope.APP

    @provide
    async def mongo_manager(self, config: MongoConfig) -> AsyncIterable[MongoManager]:
        manager = MongoManager(config=config)
        await manager.init_database()
        try:
            yield manager
        finally:
            await manager.dispose()

    @provide
    def chat_session_repository(self, manager: MongoManager) -> ChatSessionRepository:
        del manager
        return BeanieChatSessionRepository()

    @provide
    def user_profile_repository(self, manager: MongoManager) -> UserProfileRepository:
        del manager
        return BeanieUserProfileRepository()
