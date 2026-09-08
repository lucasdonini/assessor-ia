from typing import Annotated, AsyncGenerator, cast
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request

from app.application.models.user_context import UserContext
from app.infrastructure.session_coordinator import SessionCoordinator
from app.services.user_profile_service import UserProfileService
from app.services.user_service import UserService

from ..application.ports.agent_graph import AgentGraph
from ..application.ports.clock import Clock
from ..application.ports.logger import LoggerFactory, SessionContextFactory
from ..application.ports.session_history_index import SessionHistoryIndex
from ..application.ports.text_generator import TextGenerator
from ..application.repositories.chat_session_repository import ChatSessionRepository
from ..infrastructure.clock import SystemClock
from ..infrastructure.llms import fast_llm
from ..infrastructure.logger import (
    bind_user_logging_context,
    clear_session_interactions,
    create_logger,
)
from ..infrastructure.mongodb.repositories.chat_session_repository import (
    BeanieChatSessionRepository,
)
from ..infrastructure.text_generator import LLMTextGenerator
from ..services.chat_session_service import ChatSessionService
from ..services.session_summary_service import SessionSummaryService


def _get_logger_factory() -> LoggerFactory:
    return create_logger


def _get_text_generator() -> TextGenerator:
    return LLMTextGenerator(fast_llm)


def _get_clock() -> Clock:
    return SystemClock("America/Sao_Paulo")


def _get_chat_session_repository() -> ChatSessionRepository:
    return BeanieChatSessionRepository()


def _get_session_summary_service(
    logger_factory: Annotated[LoggerFactory, Depends(_get_logger_factory)],
    text_generator: Annotated[TextGenerator, Depends(_get_text_generator)],
) -> SessionSummaryService:
    logger = logger_factory(SessionSummaryService.__module__)
    return SessionSummaryService(
        text_generator=text_generator,
        logger=logger,
    )


def get_graph(request: Request) -> AgentGraph:
    graph = request.app.state.graph
    assert isinstance(graph, AgentGraph)
    return graph


def get_history_index(request: Request) -> SessionHistoryIndex:
    return cast(SessionHistoryIndex, request.app.state.history_index)


def get_chat_session_service(
    history_index: Annotated[SessionHistoryIndex, Depends(get_history_index)],
    clock: Annotated[Clock, Depends(_get_clock)],
    logger_factory: Annotated[LoggerFactory, Depends(_get_logger_factory)],
    session_repository: Annotated[
        ChatSessionRepository, Depends(_get_chat_session_repository)
    ],
    session_summary_service: Annotated[
        SessionSummaryService, Depends(_get_session_summary_service)
    ],
) -> ChatSessionService:
    logger = logger_factory(ChatSessionService.__module__)
    return ChatSessionService(
        history_index=history_index,
        service=session_summary_service,
        repository=session_repository,
        logger=logger,
        clock=clock,
    )


async def bind_session_logging_context(
    request: Request,
    session_id: str,
) -> AsyncGenerator[None, None]:
    session_context_factory = cast(
        SessionContextFactory, request.app.state.session_context_factory
    )

    request.state.session_id = session_id
    with session_context_factory(session_id):
        yield


def get_user_service(request: Request) -> UserService:
    return UserService(request.app.state.user_repository)


def get_profile_service(request: Request) -> UserProfileService:
    return cast(UserProfileService, request.app.state.profile_service)


async def get_user_context(
    user_id: Annotated[UUID, Header(alias="X-User-ID")],
    service: Annotated[UserService, Depends(get_user_service)],
    request: Request,
) -> UserContext:
    if not await service.exists(user_id):
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    request.state.user_id = str(user_id)
    return UserContext(user_id=user_id)


async def coordinate_session(
    request: Request,
    session_id: str,
    context: Annotated[UserContext, Depends(get_user_context)],
) -> AsyncGenerator[None, None]:
    coordinator: SessionCoordinator = request.app.state.session_coordinator
    with bind_user_logging_context(str(context.user_id)):
        async with coordinator.hold(session_id):
            try:
                yield
            finally:
                if getattr(request.state, "session_finalized", False):
                    clear_session_interactions(session_id)
