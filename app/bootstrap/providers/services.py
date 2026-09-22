from dishka import Provider, Scope, provide

from app.application.ports.clock import Clock
from app.application.ports.logger import LoggerFactory
from app.application.ports.profile_preferences_index import ProfilePreferencesIndex
from app.application.ports.session_history_index import SessionHistoryIndex
from app.application.ports.text_generator import TextGenerator
from app.application.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from app.application.repositories.transaction_repository import TransactionRepository
from app.application.repositories.user_profile_repository import UserProfileRepository
from app.application.repositories.user_repository import UserRepository
from app.infrastructure.clock import SystemClock
from app.infrastructure.config import AgentRuntimeConfig
from app.infrastructure.llms import fast_llm
from app.infrastructure.session_coordinator import SessionCoordinator
from app.infrastructure.text_generator import LLMTextGenerator
from app.services.chat_history_service import ChatHistoryService
from app.services.chat_session_service import ChatSessionService
from app.services.session_summary_service import SessionSummaryService
from app.services.transaction_service import TransactionService
from app.services.user_profile_service import UserProfileService
from app.services.user_service import UserService


class ServicesProvider(Provider):
    scope = Scope.APP

    @provide
    def clock(self, config: AgentRuntimeConfig) -> Clock:
        return SystemClock(config.timezone_name)

    @provide
    def text_generator(self) -> TextGenerator:
        return LLMTextGenerator(fast_llm)

    session_coordinator = provide(SessionCoordinator)

    @provide
    def profile_service(
        self,
        repository: UserProfileRepository,
        index: ProfilePreferencesIndex,
        logger_factory: LoggerFactory,
    ) -> UserProfileService:
        return UserProfileService(
            repository=repository,
            index=index,
            logger_factory=logger_factory,
        )

    @provide
    def transaction_service(
        self,
        repository: TransactionRepository,
        logger_factory: LoggerFactory,
    ) -> TransactionService:
        return TransactionService(
            repository=repository,
            logger_factory=logger_factory,
        )

    @provide
    def history_service(
        self,
        repository: ChatSessionRepository,
        history_index: SessionHistoryIndex,
        logger_factory: LoggerFactory,
    ) -> ChatHistoryService:
        return ChatHistoryService(
            repository=repository,
            history_index=history_index,
            logger_factory=logger_factory,
        )

    @provide
    def summary_service(
        self,
        text_generator: TextGenerator,
        logger_factory: LoggerFactory,
    ) -> SessionSummaryService:
        return SessionSummaryService(
            text_generator=text_generator,
            logger_factory=logger_factory,
        )

    @provide
    def chat_session_service(
        self,
        service: SessionSummaryService,
        repository: ChatSessionRepository,
        logger_factory: LoggerFactory,
        clock: Clock,
        history_index: SessionHistoryIndex,
    ) -> ChatSessionService:
        return ChatSessionService(
            service=service,
            repository=repository,
            logger_factory=logger_factory,
            clock=clock,
            history_index=history_index,
        )

    @provide
    def user_service(self, repository: UserRepository) -> UserService:
        return UserService(repository)
