from typing import Any, ClassVar, Sequence

from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph.state import CompiledStateGraph

from app.application.ports.clock import Clock
from app.application.ports.logger import Logger, LoggerFactory
from app.infrastructure.agents._core.prompting.temporal_context import (
    build_temporal_context,
)
from app.infrastructure.agents._core.schemas.specialist_output import AgendaOutput
from app.infrastructure.agents._core.state import GraphState, GraphStateKeys

from .._core.contracts.agent_factory import AgentFactory
from .._core.contracts.agent_node import AgentNode
from ..tools.agenda import agenda_evidence
from ..tools.search_history import SearchHistoryTool
from .agenda_prompt import build_agenda_prompt


class AgendaAgentNode(AgentNode):
    _agent: CompiledStateGraph
    _logger: Logger
    _clock: Clock
    name: ClassVar[str] = "agenda"

    def __init__(
        self,
        agent_factory: AgentFactory,
        logger_factory: LoggerFactory,
        clock: Clock,
        search_history_tool: SearchHistoryTool,
        agenda_tools: Sequence[BaseTool] = (),
    ) -> None:
        prompt = build_agenda_prompt(
            search_history_tool_name=search_history_tool.name,
            agenda_available=bool(agenda_tools),
        )
        self._logger = logger_factory(__name__)
        self._clock = clock
        self._agent = agent_factory(
            system_prompt=prompt,
            response_format=AgendaOutput,
            tools=(search_history_tool, *agenda_tools),
        )

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

        # type: ignore[arg-type]
        response = await self._agent.ainvoke(request_state)
        structured = response.get("structured_response")
        if isinstance(structured, AgendaOutput):
            writes = agenda_evidence().writes
            structured.escrita = writes[-1] if writes else None
            if (
                structured.intencao.lower() in {"criar", "adicionar", "registrar"}
                and not writes
            ):
                structured.resposta = (
                    "Nenhum compromisso foi registrado nesta solicitação. "
                    "Informe título, data, início e duração ou término para prosseguir."
                )
            response["messages"] = [AIMessage(content=structured.model_dump_json())]
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
