import copy
import json
import re
from collections.abc import Sequence
from typing import Any, ClassVar, cast

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph.state import CompiledStateGraph

from app.application.ports.clock import Clock
from app.application.ports.logger import Logger, LoggerFactory

from .._core.contracts.agent_factory import AgentFactory
from .._core.contracts.agent_node import AgentNode
from .._core.prompting.temporal_context import build_temporal_context
from .._core.schemas.router_output import RouterOutput, router_output_schema
from .._core.specialist import SpecialistRegistration
from .._core.state import GraphState, GraphStateKeys
from ..tools.search_history import SearchHistoryTool
from .router_prompt import build_router_prompt

SPECIALIST_JSON_KEYS = {"dominio"}


class RouterAgentNode(AgentNode):
    _agent: CompiledStateGraph
    _logger: Logger
    _clock: Clock
    _allowed_tool_names: frozenset[str]
    name: ClassVar[str] = "router"

    def __init__(
        self,
        *,
        agent_factory: AgentFactory,
        search_history_tool: SearchHistoryTool,
        logger_factory: LoggerFactory,
        specialists: Sequence[SpecialistRegistration],
        clock: Clock,
    ) -> None:
        self._logger = logger_factory(__name__)
        self._clock = clock
        self._allowed_tool_names = frozenset((search_history_tool.name,))
        self._routes = frozenset(specialist.name for specialist in specialists)
        self._agent = agent_factory(
            tools=(search_history_tool,),
            system_prompt=build_router_prompt(
                specialists=specialists,
                search_history_tool_name=search_history_tool.name,
            ),
            response_format=router_output_schema(
                tuple(specialist.name for specialist in specialists)
            ),
        )

    def _is_specialist_json(self, content: Any) -> bool:
        if not isinstance(content, str):
            return False
        text = content.strip()
        if not (text.startswith("{") and text.endswith("}")):
            return False
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False
        return isinstance(data, dict) and bool(SPECIALIST_JSON_KEYS & data.keys())

    def _filter_messages_for_router(
        self,
        messages: list[AnyMessage],
    ) -> list[AnyMessage]:
        tool_ids_to_skip: set[str] = set()
        filtered: list[AnyMessage] = []

        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                foreign_ids = {
                    cast(str, tool_call["id"])
                    for tool_call in msg.tool_calls
                    if tool_call["name"] not in self._allowed_tool_names
                    and tool_call.get("id")
                }
                tool_ids_to_skip.update(foreign_ids)

                own_calls = [
                    tool_call
                    for tool_call in msg.tool_calls
                    if tool_call["name"] in self._allowed_tool_names
                ]
                if not own_calls:
                    continue

                msg = copy.deepcopy(msg)
                msg.tool_calls = own_calls
                msg.invalid_tool_calls = []
                filtered.append(msg)
                continue

            if isinstance(msg, ToolMessage):
                if msg.tool_call_id not in tool_ids_to_skip:
                    filtered.append(msg)
                continue

            if isinstance(msg, AIMessage):
                if not self._is_specialist_json(msg.content):
                    filtered.append(msg)
                continue

            filtered.append(msg)

        return filtered

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        human = next(
            message
            for message in reversed(state["messages"])
            if isinstance(message, HumanMessage)
        )
        pending = state.get("pending_route", "")
        if pending in self._routes and re.fullmatch(
            r"(?i)\s*(?:sim|ok|confirmo|pode registrar|\d+(?:[.,]\d+)?)\s*[.!]?\s*",
            human.text,
        ):
            self._logger.info(
                "Routing pending clarification", details={"route": pending}
            )
            return {
                GraphStateKeys.ROUTE: pending,
                GraphStateKeys.PENDING_ROUTE: "",
                GraphStateKeys.CALLED_AGENTS: [self.name],
                GraphStateKeys.MESSAGES: [
                    AIMessage(
                        content=f"ROUTE={pending}\nPERGUNTA_ORIGINAL={human.text}"
                    )
                ],
            }
        input_length = len(state["messages"][-1].content)
        self._logger.info(
            "Agent called",
            details={"name": self.name, "input_length": input_length},
        )
        filtered_state: GraphState = {
            **state,
            "messages": [
                SystemMessage(content=build_temporal_context(self._clock)),
                *self._filter_messages_for_router(state["messages"]),
            ],
        }
        response = await self._agent.ainvoke(filtered_state)  # type: ignore[arg-type]
        decision = RouterOutput.model_validate(response.get("structured_response"))
        if decision.route not in self._routes and decision.route != "direct":
            raise ValueError("Router returned an unregistered specialist")
        output = (
            decision.response
            if decision.route == "direct"
            else f"ROUTE={decision.route}\nPERGUNTA_ORIGINAL={human.text}"
        )
        messages = list(response.get("messages") or [])
        if (
            messages
            and isinstance(messages[-1], AIMessage)
            and not messages[-1].tool_calls
        ):
            messages.pop()  # Native structured output is internal routing data.
        messages = self._filter_messages_for_router(messages)
        messages.append(AIMessage(content=output))
        self._logger.info(
            "Agent response",
            details={
                "from": self.name,
                "output_length": len(output),
                "route": decision.route,
            },
        )
        return {
            GraphStateKeys.MESSAGES: messages,
            GraphStateKeys.CALLED_AGENTS: [self.name],
            GraphStateKeys.ROUTE: decision.route,
            GraphStateKeys.PENDING_ROUTE: "",
        }
