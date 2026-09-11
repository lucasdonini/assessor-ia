from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide
from qdrant_client import QdrantClient

from app.application.ports.agent_graph import AgentGraph
from app.application.ports.clock import Clock
from app.application.ports.faq_search import FaqSearch
from app.application.ports.logger import (
    InteractionIncrementer,
    LoggerFactory,
    SessionContextFactory,
    TraceContextFactory,
)
from app.application.ports.profile_preferences_index import ProfilePreferencesIndex
from app.application.ports.session_history_index import SessionHistoryIndex
from app.application.ports.text_generator import TextGenerator
from app.application.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from app.application.repositories.transaction_repository import TransactionRepository
from app.application.repositories.user_profile_repository import UserProfileRepository
from app.application.repositories.user_repository import UserRepository
from app.infrastructure.agents import build_agent_graph
from app.infrastructure.clock import SystemClock
from app.infrastructure.config import (
    AgentRuntimeConfig,
    MongoConfig,
    PostgresConfig,
    ProfileIndexConfig,
)
from app.infrastructure.llms import fast_llm
from app.infrastructure.logger import (
    bind_session_context,
    bind_trace_context,
    create_logger,
    increment_interaction,
)
from app.infrastructure.mongodb.client import MongoManager
from app.infrastructure.mongodb.repositories.chat_session_repository import (
    BeanieChatSessionRepository,
)
from app.infrastructure.mongodb.repositories.user_profile_repository import (
    BeanieUserProfileRepository,
)
from app.infrastructure.postgres.pg_connection import PostgresManager
from app.infrastructure.postgres.repositories.transaction_repository import (
    SQLAlchemyTransactionRepository,
)
from app.infrastructure.postgres.repositories.user_repository import (
    SQLAlchemyUserRepository,
)
from app.infrastructure.session_coordinator import SessionCoordinator
from app.infrastructure.settings import PydanticSettings, settings
from app.infrastructure.text_generator import LLMTextGenerator
from app.infrastructure.vectorstore.client import qdrant_client
from app.infrastructure.vectorstore.config import SessionHistoryConfig
from app.infrastructure.vectorstore.embeddings import qdrant_embeddings
from app.infrastructure.vectorstore.ingestors.faq_ingestor import QDrantFaqIngestor
from app.infrastructure.vectorstore.repositories.faq_embedding_repository import (
    QDrantFaqSearch,
)
from app.infrastructure.vectorstore.repositories.profile_preferences_index import (
    QDrantProfilePreferencesIndex,
)
from app.infrastructure.vectorstore.repositories.session_history_index import (
    HistoryEmbeddings,
    QDrantSessionHistoryIndex,
)
from app.services.chat_history_service import ChatHistoryService
from app.services.chat_session_service import ChatSessionService
from app.services.session_summary_service import SessionSummaryService
from app.services.transaction_service import TransactionService
from app.services.user_profile_service import UserProfileService
from app.services.user_service import UserService


async def build_history_index(
    client: QdrantClient,
    embeddings: HistoryEmbeddings,
    config: SessionHistoryConfig,
    logger_factory: LoggerFactory,
) -> SessionHistoryIndex:
    index = QDrantSessionHistoryIndex(
        client=client,
        embeddings=embeddings,
        config=config,
        logger_factory=logger_factory,
    )
    await index.validate_collection()
    return index


class ApplicationProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> PydanticSettings:
        return settings

    @provide
    def logger_factory(self) -> LoggerFactory:
        return create_logger

    @provide
    def trace_context_factory(self) -> TraceContextFactory:
        return bind_trace_context

    @provide
    def session_context_factory(self) -> SessionContextFactory:
        return bind_session_context

    @provide
    def interaction_incrementer(self) -> InteractionIncrementer:
        return increment_interaction

    @provide
    def qdrant_client(self) -> QdrantClient:
        return qdrant_client

    @provide
    def history_embeddings(self) -> HistoryEmbeddings:
        return qdrant_embeddings

    @provide
    def history_config(self, config: PydanticSettings) -> SessionHistoryConfig:
        return SessionHistoryConfig(
            collection_name=config.history_collection_name,
            dimensions=config.embedding_dimmensions,
        )

    @provide
    def mongo_config(self, config: PydanticSettings) -> MongoConfig:
        return MongoConfig(
            uri=config.mongodb_uri.get_secret_value(),
            database_name=config.mongodb_dbname.get_secret_value(),
        )

    @provide
    def postgres_config(self, config: PydanticSettings) -> PostgresConfig:
        return PostgresConfig(url=config.postgres_url.get_secret_value())

    @provide
    def agent_runtime_config(self, config: PydanticSettings) -> AgentRuntimeConfig:
        return AgentRuntimeConfig(
            timezone_name=config.app_timezone,
            execution_timeout_seconds=config.agent_execution_timeout_seconds,
        )

    @provide
    def profile_index_config(self, config: PydanticSettings) -> ProfileIndexConfig:
        return ProfileIndexConfig(dimensions=config.embedding_dimmensions)

    history_index = provide(
        staticmethod(build_history_index), provides=SessionHistoryIndex
    )

    @provide
    async def mongo_manager(self, config: MongoConfig) -> AsyncIterable[MongoManager]:
        manager = MongoManager(config=config)
        await manager.init_database()
        try:
            yield manager
        finally:
            await manager.dispose()

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
    def chat_session_repository(self, manager: MongoManager) -> ChatSessionRepository:
        del manager
        return BeanieChatSessionRepository()

    @provide
    def user_profile_repository(self, manager: MongoManager) -> UserProfileRepository:
        del manager
        return BeanieUserProfileRepository()

    @provide
    def user_repository(self, manager: PostgresManager) -> UserRepository:
        return SQLAlchemyUserRepository(manager.session_factory)

    @provide
    def transaction_repository(self, manager: PostgresManager) -> TransactionRepository:
        return SQLAlchemyTransactionRepository(manager.session_factory)

    @provide
    async def profile_index(
        self,
        client: QdrantClient,
        embeddings: HistoryEmbeddings,
        config: ProfileIndexConfig,
    ) -> ProfilePreferencesIndex:
        index = QDrantProfilePreferencesIndex(
            client=client,
            embeddings=embeddings,
            dimensions=config.dimensions,
        )
        await index.initialize()
        return index

    @provide
    def clock(self, config: AgentRuntimeConfig) -> Clock:
        return SystemClock(config.timezone_name)

    @provide
    def text_generator(self) -> TextGenerator:
        return LLMTextGenerator(fast_llm)

    session_coordinator = provide(SessionCoordinator)

    @provide
    def faq_ingestor(self, logger_factory: LoggerFactory) -> QDrantFaqIngestor:
        return QDrantFaqIngestor(logger_factory=logger_factory)

    @provide
    def faq_search(self, logger_factory: LoggerFactory) -> FaqSearch:
        return QDrantFaqSearch(logger_factory=logger_factory)

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

    @provide
    def graph(
        self,
        transaction_service: TransactionService,
        profile_service: UserProfileService,
        chat_history_service: ChatHistoryService,
        faq_search: FaqSearch,
        text_generator: TextGenerator,
        logger_factory: LoggerFactory,
        trace_context_factory: TraceContextFactory,
        interaction_incrementer: InteractionIncrementer,
        clock: Clock,
        config: AgentRuntimeConfig,
    ) -> AgentGraph:
        return build_agent_graph(
            transaction_service=transaction_service,
            profile_service=profile_service,
            chat_history_service=chat_history_service,
            faq_search=faq_search,
            text_generator=text_generator,
            logger_factory=logger_factory,
            trace_context_factory=trace_context_factory,
            interaction_incrementer=interaction_incrementer,
            clock=clock,
            execution_timeout_seconds=config.execution_timeout_seconds,
        )
