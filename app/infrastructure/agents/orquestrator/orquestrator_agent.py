from typing import Any, ClassVar

from langchain_core.messages import SystemMessage
from langgraph.graph.state import CompiledStateGraph

from app.application.ports.clock import Clock
from app.application.ports.logger import Logger, LoggerFactory

from .._core.contracts.agent_factory import AgentFactory
from .._core.contracts.agent_node import AgentNode
from .._core.prompting.temporal_context import build_temporal_context
from .._core.state import GraphState, GraphStateKeys
from .orquestrator_prompt import PROMPT


class OrquestratorAgentNode(AgentNode):
    _agent: CompiledStateGraph
    _logger: Logger
    _clock: Clock
    name: ClassVar[str] = "orquestrator"

    def __init__(
        self,
        *,
        agent_factory: AgentFactory,
        logger_factory: LoggerFactory,
        clock: Clock,
    ) -> None:
        self._logger = logger_factory(__name__)
        self._clock = clock
        self._agent = agent_factory(system_prompt=PROMPT)

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        input_length = len(state["messages"][-1].content)
        self._logger.info(
            "Agent called",
            details={"name": self.name, "input_length": input_length},
        )
        request_state: GraphState = {
            **state,
            "messages": [
                SystemMessage(content=build_temporal_context(self._clock)),
                *state["messages"],
            ],
        }
        response = await self._agent.ainvoke(request_state)  # type: ignore[arg-type]
        last = (response.get("messages") or [None])[-1]
        output_length = len(last.content) if last and last.content else 0
        self._logger.info(
            "Agent response",
            details={"from": self.name, "output_length": output_length},
        )
        return {
            GraphStateKeys.MESSAGES: response.get("messages") or [],
            GraphStateKeys.CALLED_AGENTS: [self.name],
        }
