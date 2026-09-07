from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.application.models.user_context import UserContext
from app.application.ports.agent_graph import AgentGraph
from app.domain.exception.chat_session import ChatSessionException
from app.domain.model.chat_entry import HumanMessage
from app.services.chat_session_service import ChatSessionService

from ..dependencies import (
    bind_session_logging_context,
    get_chat_session_service,
    get_graph,
    get_user_context,
)
from ..schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", dependencies=[Depends(bind_session_logging_context)])


@router.post("/{session_id}")
async def chat(
    session_id: str,
    context: Annotated[UserContext, Depends(get_user_context)],
    user_input: Annotated[ChatRequest, Body()],
    graph: Annotated[AgentGraph, Depends(get_graph)],
    session_service: Annotated[ChatSessionService, Depends(get_chat_session_service)],
) -> ChatResponse:
    try:
        await session_service.get_or_create_session(session_id, user_id=context.user_id)

        question = HumanMessage(content=user_input.message)
        await session_service.save_message(
            session_id=session_id, user_id=context.user_id, message=question
        )

        response = await graph.execute_agent_flux(question, session_id, context=context)
        await session_service.save_message(
            session_id=session_id, user_id=context.user_id, message=response.message
        )

        return ChatResponse(
            session_id=session_id,
            content=response.message.content,
            called_agents=list(response.called_agents),
        )
    except TimeoutError:
        raise
    except ChatSessionException:
        raise
    except Exception as e:
        await session_service.save_error(session_id, e, user_id=context.user_id)
        raise
