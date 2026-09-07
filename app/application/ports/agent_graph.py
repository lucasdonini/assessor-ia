from typing import Protocol, runtime_checkable

from app.application.models.agent_execution import AgentExecutionResult
from app.application.models.user_context import UserContext
from app.domain.model.chat_entry import HumanMessage


@runtime_checkable
class AgentGraph(Protocol):
    async def execute_agent_flux(
        self, message: HumanMessage, session_id: str, *, context: UserContext
    ) -> AgentExecutionResult: ...
