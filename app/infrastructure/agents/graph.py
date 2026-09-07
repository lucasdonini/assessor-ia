import asyncio
import time
import uuid
from collections.abc import Sequence
from typing import Any, cast

from langchain_core.messages import AIMessage as LangGraphAIMessage
from langchain_core.messages import HumanMessage as LangGraphHumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Overwrite

from app.application.models.agent_execution import AgentExecutionResult
from app.application.models.user_context import UserContext
from app.application.ports.logger import (
    InteractionIncrementer,
    LoggerFactory,
    TraceContextFactory,
)
from app.domain.model.chat_entry import AssistantMessage, HumanMessage

from ._core.contracts.agent_node import AgentNode
from ._core.specialist import SpecialistRegistration
from ._core.state import GraphState, GraphStateKeys
from ._core.user_context import bind_user_context


class AgentGraphImpl:
    def __init__(
        self,
        *,
        input_guardrail: AgentNode,
        router: AgentNode,
        specialists: Sequence[SpecialistRegistration],
        orquestrator: AgentNode,
        output_guardrail: AgentNode,
        execution_timeout_seconds: float,
        logger_factory: LoggerFactory,
        trace_context_factory: TraceContextFactory,
        interaction_incrementer: InteractionIncrementer,
    ) -> None:
        self._input_guardrail = input_guardrail
        self._router = router
        self._specialists = tuple(specialists)
        self._orquestrator = orquestrator
        self._output_guardrail = output_guardrail
        self._execution_timeout_seconds = execution_timeout_seconds
        self._logger = logger_factory(__name__)
        self._trace_context_factory = trace_context_factory
        self._interaction_incrementer = interaction_incrementer
        self._specialists_by_name = {
            specialist.name: specialist for specialist in self._specialists
        }

        self._validate_nodes()
        self._graph = StateGraph(GraphState)
        self._add_nodes()
        self._add_edges()
        self._add_conditional_edges()
        self._agent_flux = self._compile_graph()

    def _validate_nodes(self) -> None:
        nodes = [
            self._input_guardrail,
            self._router,
            *(specialist.node for specialist in self._specialists),
            self._orquestrator,
            self._output_guardrail,
        ]
        names = [node.name for node in nodes]
        duplicate_names = {name for name in names if names.count(name) > 1}
        if duplicate_names:
            duplicates = ", ".join(sorted(duplicate_names))
            raise ValueError(f"Agent node names must be unique: {duplicates}")
        if not self._specialists:
            raise ValueError("Agent graph requires at least one specialist")

    def _add_nodes(self) -> None:
        self._graph.add_node(
            self._input_guardrail.name,
            self._timed_node(self._input_guardrail),
        )
        self._graph.add_node(self._router.name, self._timed_node(self._router))
        for specialist in self._specialists:
            self._graph.add_node(
                specialist.name,
                self._timed_node(specialist.node),
            )
        self._graph.add_node(
            self._orquestrator.name,
            self._timed_node(self._orquestrator),
        )
        self._graph.add_node(
            self._output_guardrail.name,
            self._timed_node(self._output_guardrail),
        )

    def _timed_node(
        self,
        node: AgentNode,
    ) -> RunnableLambda[GraphState, dict[GraphStateKeys, Any]]:
        async def invoke(state: GraphState) -> dict[GraphStateKeys, Any]:
            start_time = time.perf_counter()
            try:
                return await node(state)
            finally:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000)
                self._logger.debug(
                    "Function finished",
                    details={
                        "function": node.name,
                        "elapsed_ms": elapsed_ms,
                        "kind": "Async",
                    },
                )

        return RunnableLambda(invoke)

    def _add_edges(self) -> None:
        self._graph.add_edge(START, self._input_guardrail.name)
        for specialist in self._specialists:
            self._graph.add_edge(specialist.name, specialist.destination)
        self._graph.add_edge(self._orquestrator.name, self._output_guardrail.name)
        self._graph.add_edge(self._output_guardrail.name, END)

    def _add_conditional_edges(self) -> None:
        def choose_specialist(state: GraphState) -> str:
            text = state["messages"][-1].text.strip()
            if not text.startswith("ROUTE="):
                return END

            route = text.split("\n", 1)[0].split("=", 1)[1].strip()
            return route if route in self._specialists_by_name else END

        def redirect_from_input_guardrail(state: GraphState) -> str:
            route = state["route"]
            return self._router.name if route == self._router.name else END

        self._graph.add_conditional_edges(self._router.name, choose_specialist)
        self._graph.add_conditional_edges(
            self._input_guardrail.name,
            redirect_from_input_guardrail,
        )

    def _compile_graph(self) -> CompiledStateGraph:
        serializer = JsonPlusSerializer(
            allowed_msgpack_modules=[(GraphState.__module__, GraphStateKeys.__name__)]
        )
        memory = MemorySaver(serde=serializer)
        return self._graph.compile(checkpointer=memory)

    async def execute_agent_flux(
        self,
        user_input: HumanMessage,
        session_id: str,
        *,
        context: UserContext,
    ) -> AgentExecutionResult:
        self._interaction_incrementer()
        trace_id = str(uuid.uuid4())
        with self._trace_context_factory(trace_id), bind_user_context(context):
            message = LangGraphHumanMessage(id=trace_id, content=user_input.content)
            self._logger.info(
                "User input received",
                details={"input_length": len(user_input.content)},
            )

            initial_state: dict[str, object] = {
                "messages": [message],
                # Reset this turn's trace without clearing conversation memory.
                "called_agents": Overwrite([]),
                "route": "",
                "pii_map": {},
            }

            try:
                async with asyncio.timeout(self._execution_timeout_seconds):
                    final_state_raw = await self._agent_flux.ainvoke(
                        initial_state,
                        config={
                            "configurable": {
                                "thread_id": f"{context.user_id}:{session_id}"
                            }
                        },
                    )
            except TimeoutError:
                self._logger.error(
                    "Agent chain timed out",
                    details={"timeout_seconds": self._execution_timeout_seconds},
                )
                raise
            final_state = cast(GraphState, final_state_raw)

            self._logger.info(
                "Agent chain completed",
                details={"chain": " → ".join(final_state["called_agents"])},
            )

            last = final_state["messages"][-1]
            if not isinstance(last, LangGraphAIMessage):
                raise ValueError(
                    "Expected last message to be AIMessage, "
                    f"received {type(last).__name__!r}"
                )
            if not isinstance(last.content, str):
                raise ValueError(
                    "Expected last message content to be str, "
                    f"received {type(last.content).__name__!r}"
                )
            return AgentExecutionResult(
                message=AssistantMessage(content=last.content),
                called_agents=tuple(final_state["called_agents"]),
            )
