from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.infrastructure.postgres.repositories.user_repository import (
    SQLAlchemyUserRepository,
)

from .infrastructure.agents import build_agent_graph
from .infrastructure.clock import SystemClock
from .infrastructure.llms import fast_llm
from .infrastructure.logger import (
    bind_session_context,
    bind_trace_context,
    create_logger,
    increment_interaction,
    setup_logger,
)
from .infrastructure.mongodb.client import MongoManager
from .infrastructure.mongodb.repositories.chat_session_repository import (
    BeanieChatSessionRepository,
)
from .infrastructure.postgres.pg_connection import PostgresManager
from .infrastructure.postgres.repositories.transaction_repository import (
    SQLAlchemyTransactionRepository,
)
from .infrastructure.settings import settings
from .infrastructure.text_generator import LLMTextGenerator
from .infrastructure.vectorstore.ingestors.faq_ingestor import QDrantFaqIngestor
from .infrastructure.vectorstore.repositories.faq_embedding_repository import (
    QDrantFaqSearch,
)
from .services.chat_history_service import ChatHistoryService
from .services.transaction_service import TransactionService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logger()
    settings.validate_envs()

    faq_ingestor = QDrantFaqIngestor(logger_factory=create_logger)
    faq_ingestor.ingest()

    mongo_manager = MongoManager(settings=settings)
    await mongo_manager.init_database()
    chat_session_repository = BeanieChatSessionRepository()
    postgres_manager = PostgresManager(settings.postgres_url.get_secret_value())
    app.state.user_repository = SQLAlchemyUserRepository(
        postgres_manager.session_factory
    )
    clock = SystemClock(settings.app_timezone)

    text_generator = LLMTextGenerator(fast_llm)
    transaction_repository = SQLAlchemyTransactionRepository(
        session_factory=postgres_manager.session_factory
    )
    transaction_service = TransactionService(
        repository=transaction_repository,
        logger=create_logger(TransactionService.__module__),
    )
    chat_history_service = ChatHistoryService(
        repository=chat_session_repository,
        logger=create_logger(ChatHistoryService.__module__),
    )

    faq_search = QDrantFaqSearch(logger_factory=create_logger)

    graph = build_agent_graph(
        transaction_service=transaction_service,
        chat_history_service=chat_history_service,
        faq_search=faq_search,
        text_generator=text_generator,
        logger_factory=create_logger,
        trace_context_factory=bind_trace_context,
        interaction_incrementer=increment_interaction,
        clock=clock,
        execution_timeout_seconds=settings.agent_execution_timeout_seconds,
    )

    app.state.graph = graph
    app.state.session_context_factory = bind_session_context

    try:
        yield
    finally:
        await postgres_manager.dispose()
