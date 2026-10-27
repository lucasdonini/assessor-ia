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
from langsmith import tracing_context

from app.application.models.agent_execution import AgentExecutionResult
from app.application.models.user_context import UserContext
from app.application.ports.logger import (
    InteractionIncrementer,
    LoggerFactory,
    TraceContextFactory,
)
from app.domain.model.chat_entry import AssistantMessage, HumanMessage
from app.infrastructure.observability import (
    TurnTelemetry,
    observe_financial_outcomes,
    observe_node,
    observe_route,
)
from app.infrastructure.tracing import PrivateTracing

from ._core.contracts.agent_node import AgentNode
from ._core.evidence import current_evidence, evidence_execution
from ._core.specialist import SpecialistRegistration
from ._core.state import GraphState, GraphStateKeys
from ._core.user_context import bind_user_context
from .evidence_judge import receipt
from .tools.agenda import AgendaEvidence, agenda_execution, creation_message


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
        telemetry: TurnTelemetry | None = None,
        tracing: PrivateTracing | None = None,
        evidence_judge: AgentNode | None = None,
    ) -> None:
        self._input_guardrail = input_guardrail
        self._router = router
        self._specialists = tuple(specialists)
        self._orquestrator = orquestrator
        self._output_guardrail = output_guardrail
        self._evidence_judge = evidence_judge
        self._execution_timeout_seconds = execution_timeout_seconds
        self._logger = logger_factory(__name__)
        self._trace_context_factory = trace_context_factory
        self._interaction_incrementer = interaction_incrementer
        self._telemetry = telemetry or TurnTelemetry(logger_factory)
        self._tracing = tracing
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
        if self._evidence_judge:
            names.append(self._evidence_judge.name)
        duplicate_names = {name for name in names if names.count(name) > 1}
        if duplicate_names:
            duplicates = ", ".join(sorted(duplicate_names))
            raise ValueError(f"Agent node names must be unique: {duplicates}")
        if not self._specialists:
            raise ValueError("Agent graph requires at least one specialist")

    def _add_nodes(self) -> None:
        if self._evidence_judge:
            self._graph.add_node(
                self._evidence_judge.name, self._timed_node(self._evidence_judge)
            )
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
                with observe_node(node.name):
                    if self._evidence_judge and node is not self._evidence_judge:
                        fixed = receipt()
                        if fixed is not None:
                            return {
                                GraphStateKeys.MESSAGES: [
                                    LangGraphAIMessage(content=fixed)
                                ],
                                GraphStateKeys.CALLED_AGENTS: [node.name],
                            }
                    try:
                        return await node(state)
                    except Exception:
                        fixed = receipt() if self._evidence_judge else None
                        if fixed is None:
                            raise
                        return {
                            GraphStateKeys.MESSAGES: [
                                LangGraphAIMessage(content=fixed)
                            ],
                            GraphStateKeys.CALLED_AGENTS: [node.name],
                        }
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
            destination = (
                self._evidence_judge.name
                if self._evidence_judge and specialist.destination == END
                else specialist.destination
            )
            self._graph.add_edge(specialist.name, destination)
        self._graph.add_edge(self._orquestrator.name, self._output_guardrail.name)
        self._graph.add_edge(
            self._output_guardrail.name,
            self._evidence_judge.name if self._evidence_judge else END,
        )
        if self._evidence_judge:
            self._graph.add_edge(self._evidence_judge.name, END)

    def _add_conditional_edges(self) -> None:
        def choose_specialist(state: GraphState) -> str:
            text = state["messages"][-1].text.strip()
            if not text.startswith("ROUTE="):
                observe_route("direct")
                return self._evidence_judge.name if self._evidence_judge else END

            route = text.split("\n", 1)[0].split("=", 1)[1].strip()
            observe_route(route if route in self._specialists_by_name else "direct")
            return (
                route
                if route in self._specialists_by_name
                else (self._evidence_judge.name if self._evidence_judge else END)
            )

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
        with (
            self._trace_context_factory(trace_id),
            bind_user_context(context),
            agenda_execution() as agenda_evidence,
            evidence_execution(context.user_id, (user_input.content,)),
        ):
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

            with (
                self._tracing.scope()
                if self._tracing
                else tracing_context(enabled=False),
            ):
                async with self._telemetry.persisted_turn(
                    trace_id, str(context.user_id), session_id
                ):
                    return await self._execute_turn(
                        initial_state, trace_id, context, session_id, agenda_evidence
                    )

    async def _execute_turn(
        self,
        initial_state: dict[str, object],
        trace_id: str,
        context: UserContext,
        session_id: str,
        agenda_evidence: AgendaEvidence,
    ) -> AgentExecutionResult:
        try:
            async with asyncio.timeout(self._execution_timeout_seconds):
                if self._evidence_judge:
                    snapshot = await self._agent_flux.aget_state(
                        {
                            "configurable": {
                                "thread_id": f"{context.user_id}:{session_id}"
                            }
                        }
                    )
                    prior = tuple(
                        item.text
                        for item in snapshot.values.get("messages", [])
                        if isinstance(item, LangGraphHumanMessage)
                    )[-5:]
                    evidence = current_evidence()
                    if evidence:
                        evidence.financial.statements = (
                            *prior,
                            evidence.financial.statements[-1],
                        )
                final_state_raw = await self._agent_flux.ainvoke(
                    initial_state,
                    config={
                        "run_id": uuid.UUID(trace_id),
                        "callbacks": [
                            self._telemetry.callback,
                            *(self._tracing.callbacks() if self._tracing else []),
                        ],
                        "metadata": {"turn_id": trace_id},
                        "configurable": {
                            "thread_id": f"{context.user_id}:{session_id}"
                        },
                    },
                )
        except TimeoutError:
            self._logger.error(
                "Agent chain timed out",
                details={"timeout_seconds": self._execution_timeout_seconds},
            )
            fixed = receipt() if self._evidence_judge else None
            if fixed and self._evidence_judge:
                # A confirmed outcome needs no model call, even if generation
                # exhausted the graph deadline. Execute the terminal node so
                # called_agents and node timing describe an actual invocation.
                await self._timed_node(self._evidence_judge).ainvoke(
                    {"messages": [], "called_agents": [], "route": "", "pii_map": {}}
                )
                evidence = current_evidence()
                if evidence:
                    observe_financial_outcomes(evidence.financial.outcomes)
                return AgentExecutionResult(
                    message=AssistantMessage(content=fixed),
                    called_agents=("evidence_judge",),
                )
            raise
        final_state = cast(GraphState, final_state_raw)
        evidence = current_evidence()
        if evidence:
            observe_financial_outcomes(evidence.financial.outcomes)

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
            message=AssistantMessage(
                content=(
                    "\n\n".join(
                        creation_message(item) for item in agenda_evidence.writes
                    )
                    if agenda_evidence.writes and not self._evidence_judge
                    else last.content
                )
            ),
            called_agents=tuple(final_state["called_agents"]),
        )
