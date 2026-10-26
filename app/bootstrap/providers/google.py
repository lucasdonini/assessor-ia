from dishka import Provider, Scope, provide

from app.application.ports.calendar import CalendarGateway
from app.application.ports.google_oauth import GoogleOAuth, TokenCipher
from app.application.repositories.auth_repository import (
    AuthRepository,
    AuthStateRepository,
)
from app.application.repositories.event_repository import EventRepository
from app.infrastructure.config import GoogleConfig
from app.infrastructure.google_calendar import GoogleCalendarGateway
from app.infrastructure.google_oauth import FernetTokenCipher, GoogleOAuthAdapter
from app.infrastructure.mongodb.client import MongoManager
from app.infrastructure.mongodb.repositories.auth_state_repository import (
    MongoAuthStateRepository,
)
from app.infrastructure.postgres.pg_connection import PostgresManager
from app.infrastructure.postgres.repositories.auth_repository import (
    SQLAlchemyAuthRepository,
)
from app.infrastructure.postgres.repositories.event_repository import (
    SQLAlchemyEventRepository,
)
from app.services.auth_service import AuthService
from app.services.event_service import EventService


class GoogleProvider(Provider):
    scope = Scope.APP

    @provide
    def oauth(self, config: GoogleConfig) -> GoogleOAuth:
        return GoogleOAuthAdapter(config)

    @provide
    def cipher(self, config: GoogleConfig) -> TokenCipher:
        return FernetTokenCipher(config)

    @provide
    def repository(self, manager: PostgresManager) -> AuthRepository:
        return SQLAlchemyAuthRepository(manager.session_factory)

    @provide
    async def state_repository(self, manager: MongoManager) -> AuthStateRepository:
        repository = MongoAuthStateRepository(manager.database())
        await repository.initialize()
        return repository

    service = provide(AuthService)

    @provide
    def event_repository(self, manager: PostgresManager) -> EventRepository:
        return SQLAlchemyEventRepository(manager.session_factory)

    @provide
    def calendar(self, auth: AuthService, config: GoogleConfig) -> CalendarGateway:
        return GoogleCalendarGateway(auth, config)

    event_service = provide(EventService)
