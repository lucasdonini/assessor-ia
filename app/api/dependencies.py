from typing import Annotated, AsyncGenerator
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends, Header, HTTPException, Request

from app.application.models.user_context import UserContext
from app.application.ports.agent_graph import AgentGraph
from app.application.ports.logger import SessionContextFactory
from app.application.ports.session_history_index import SessionHistoryIndex
from app.infrastructure.logger import (
    bind_user_logging_context,
    clear_session_interactions,
)
from app.infrastructure.session_coordinator import SessionCoordinator
from app.services.chat_session_service import ChatSessionService
from app.services.user_profile_service import UserProfileService
from app.services.user_service import UserService


@inject
def get_graph(graph: FromDishka[AgentGraph]) -> AgentGraph:
    return graph


@inject
def get_history_index(index: FromDishka[SessionHistoryIndex]) -> SessionHistoryIndex:
    return index


@inject
def get_chat_session_service(
    service: FromDishka[ChatSessionService],
) -> ChatSessionService:
    return service


@inject
async def bind_session_logging_context(
    request: Request,
    session_id: str,
    session_context_factory: FromDishka[SessionContextFactory],
) -> AsyncGenerator[None, None]:
    request.state.session_id = session_id
    with session_context_factory(session_id):
        yield


@inject
def get_user_service(service: FromDishka[UserService]) -> UserService:
    return service


@inject
def get_profile_service(
    service: FromDishka[UserProfileService],
) -> UserProfileService:
    return service


async def get_user_context(
    user_id: Annotated[UUID, Header(alias="X-User-ID")],
    service: Annotated[UserService, Depends(get_user_service)],
    request: Request,
) -> UserContext:
    if not await service.exists(user_id):
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    request.state.user_id = str(user_id)
    return UserContext(user_id=user_id)


@inject
async def coordinate_session(
    request: Request,
    session_id: str,
    context: Annotated[UserContext, Depends(get_user_context)],
    coordinator: FromDishka[SessionCoordinator],
) -> AsyncGenerator[None, None]:
    with bind_user_logging_context(str(context.user_id)):
        async with coordinator.hold(session_id):
            try:
                yield
            finally:
                if getattr(request.state, "session_finalized", False):
                    clear_session_interactions(session_id)
