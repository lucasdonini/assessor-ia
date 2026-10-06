import asyncio
from contextlib import nullcontext
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage as GraphHumanMessage
from langgraph.graph import END

from app.application.models.user_context import UserContext
from app.application.ports.logger import Logger
from app.domain.model.chat_entry import AssistantMessage, HumanMessage
from app.infrastructure.agents._core.contracts.agent_node import AgentNode
from app.infrastructure.agents._core.specialist import SpecialistRegistration
from app.infrastructure.agents._core.state import GraphState, GraphStateKeys
from app.infrastructure.agents.graph import AgentGraphImpl
from app.infrastructure.observability import InMemoryObservability
from app.services.monitoring_service import MonitoringService
from tests.user_identity import TEST_USER_ID


class _InputGuardrail(AgentNode):
    name: ClassVar[str] = "input_guardrail"

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        blocked = state["messages"][-1].content == "blocked"
        result: dict[GraphStateKeys, Any] = {
            GraphStateKeys.CALLED_AGENTS: [self.name],
            GraphStateKeys.ROUTE: END if blocked else "router",
        }
        if blocked:
            result[GraphStateKeys.MESSAGES] = [AIMessage(content="Bloqueado")]
        return result


class _Router(AgentNode):
    name: ClassVar[str] = "router"

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        question = state["messages"][-1].content
        return {
            GraphStateKeys.CALLED_AGENTS: [self.name],
            GraphStateKeys.MESSAGES: [AIMessage(content=f"ROUTE={question}")],
        }


class _Financial(AgentNode):
    name: ClassVar[str] = "financial"

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        return {
            GraphStateKeys.CALLED_AGENTS: [self.name],
            GraphStateKeys.MESSAGES: [AIMessage(content=self.name)],
        }


class _Agenda(_Financial):
    name: ClassVar[str] = "agenda"


class _Orquestrator(_Financial):
    name: ClassVar[str] = "orquestrator"


class _OutputGuardrail(_Financial):
    name: ClassVar[str] = "output_guardrail"


@pytest.mark.asyncio
async def test_observed_graph_records_selected_edge_and_turn_local_nodes(graph):
    collector = InMemoryObservability()
    graph._recorder = collector
    await graph.execute_agent_flux(
        HumanMessage(content="financial"), "same", context=UserContext(TEST_USER_ID)
    )
    await graph.execute_agent_flux(
        HumanMessage(content="unknown"), "same", context=UserContext(TEST_USER_ID)
    )
    turns = collector.snapshot(str(TEST_USER_ID)).turns
    assert [turn.route for turn in turns] == ["financial", "none"]
    assert [n.name for n in turns[0].nodes] == [
        "input_guardrail",
        "router",
        "financial",
        "orquestrator",
        "output_guardrail",
    ]
    assert [n.name for n in turns[1].nodes] == ["input_guardrail", "router"]
    assert turns[0].turn_id != turns[1].turn_id


@pytest.mark.asyncio
async def test_observed_graph_timeout_and_cancellation(graph, monkeypatch):
    collector = InMemoryObservability()
    graph._recorder = collector

    graph._execution_timeout_seconds = 0.01

    # Accept config as in the production graph call.
    async def invoke(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(graph._agent_flux, "ainvoke", invoke)
    with pytest.raises(TimeoutError):
        await graph.execute_agent_flux(
            HumanMessage(content="x"), "s", context=UserContext(TEST_USER_ID)
        )
    assert collector.snapshot(str(TEST_USER_ID)).turns[0].status == "error"
    assert collector.snapshot(str(TEST_USER_ID)).in_flight == 0
    graph._execution_timeout_seconds = 30
    task = asyncio.create_task(
        graph.execute_agent_flux(
            HumanMessage(content="x"), "s", context=UserContext(TEST_USER_ID)
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert collector.snapshot(str(TEST_USER_ID)).turns[-1].status == "cancelled"
    assert collector.snapshot(str(TEST_USER_ID)).in_flight == 0


@pytest.mark.asyncio
async def test_collector_enter_failure_does_not_change_chat(graph):
    collector = MagicMock()
    collector.turn.side_effect = RuntimeError("collector failed")
    collector.node.side_effect = RuntimeError("collector failed")
    collector.callbacks = ()
    graph._recorder = collector
    result = await graph.execute_agent_flux(
        HumanMessage(content="financial"), "s", context=UserContext(TEST_USER_ID)
    )
    assert result.message.content == "output_guardrail"


@pytest.mark.asyncio
async def test_classifier_degradation_is_error_without_changing_reply(
    graph, monkeypatch
):
    collector = InMemoryObservability()
    graph._recorder = collector

    async def classify(self, state):
        return {
            GraphStateKeys.ROUTE: END,
            GraphStateKeys.GUARDRAIL_REASON: "classificador_indisponivel",
            GraphStateKeys.CALLED_AGENTS: [self.name],
            GraphStateKeys.MESSAGES: [AIMessage(content="Tente novamente.")],
        }

    monkeypatch.setattr(_InputGuardrail, "__call__", classify)
    result = await graph.execute_agent_flux(
        HumanMessage(content="x"), "s", context=UserContext(TEST_USER_ID)
    )
    assert result.message.content == "Tente novamente."
    assert (
        MonitoringService(collector).get_monitor(str(TEST_USER_ID)).summary.errors == 1
    )


@pytest.fixture
def graph() -> AgentGraphImpl:
    return AgentGraphImpl(
        input_guardrail=_InputGuardrail(),
        router=_Router(),
        specialists=[
            SpecialistRegistration(node, node.name, "orquestrator")
            for node in (_Financial(), _Agenda())
        ],
        orquestrator=_Orquestrator(),
        output_guardrail=_OutputGuardrail(),
        execution_timeout_seconds=5,
        logger_factory=lambda _: MagicMock(spec=Logger),
        trace_context_factory=lambda _: nullcontext(),
        interaction_incrementer=lambda: 1,
    )


@pytest.mark.asyncio
async def test_each_turn_resets_agents_but_preserves_messages(
    graph: AgentGraphImpl,
) -> None:
    first = await graph.execute_agent_flux(
        HumanMessage(content="financial"), "session", context=UserContext(TEST_USER_ID)
    )
    second = await graph.execute_agent_flux(
        HumanMessage(content="agenda"), "session", context=UserContext(TEST_USER_ID)
    )

    assert first.message == AssistantMessage(content="output_guardrail")
    assert first.called_agents == (
        "input_guardrail",
        "router",
        "financial",
        "orquestrator",
        "output_guardrail",
    )
    assert second.called_agents == (
        "input_guardrail",
        "router",
        "agenda",
        "orquestrator",
        "output_guardrail",
    )
    snapshot = await graph._agent_flux.aget_state(
        {"configurable": {"thread_id": f"{TEST_USER_ID}:session"}}
    )
    assert snapshot.values["called_agents"] == list(second.called_agents)
    assert [
        message.content
        for message in snapshot.values["messages"]
        if isinstance(message, GraphHumanMessage)
    ] == ["financial", "agenda"]
    graph._logger.info.assert_called_with(
        "Agent chain completed",
        details={"chain": " → ".join(second.called_agents)},
    )


@pytest.mark.asyncio
async def test_blocked_turn_only_reports_input_guardrail_and_next_turn_recovers(
    graph: AgentGraphImpl,
) -> None:
    await graph.execute_agent_flux(
        HumanMessage(content="financial"), "session", context=UserContext(TEST_USER_ID)
    )
    blocked = await graph.execute_agent_flux(
        HumanMessage(content="blocked"), "session", context=UserContext(TEST_USER_ID)
    )

    assert blocked.message.content == "Bloqueado"
    assert blocked.called_agents == ("input_guardrail",)

    following = await graph.execute_agent_flux(
        HumanMessage(content="agenda"), "session", context=UserContext(TEST_USER_ID)
    )
    assert following.called_agents == (
        "input_guardrail",
        "router",
        "agenda",
        "orquestrator",
        "output_guardrail",
    )


@pytest.mark.asyncio
async def test_router_early_exit_does_not_inherit_previous_specialists(
    graph: AgentGraphImpl,
) -> None:
    await graph.execute_agent_flux(
        HumanMessage(content="financial"), "session", context=UserContext(TEST_USER_ID)
    )
    result = await graph.execute_agent_flux(
        HumanMessage(content="unknown"), "session", context=UserContext(TEST_USER_ID)
    )

    assert result.called_agents == ("input_guardrail", "router")


@pytest.mark.asyncio
async def test_concurrent_users_have_distinct_checkpoints(graph):
    import asyncio
    from uuid import uuid4

    other = uuid4()
    await asyncio.gather(
        graph.execute_agent_flux(
            HumanMessage(content="financial"), "same", context=UserContext(TEST_USER_ID)
        ),
        graph.execute_agent_flux(
            HumanMessage(content="agenda"), "same", context=UserContext(other)
        ),
    )
    for owner, expected in [(TEST_USER_ID, "financial"), (other, "agenda")]:
        snapshot = await graph._agent_flux.aget_state(
            {"configurable": {"thread_id": f"{owner}:same"}}
        )
        assert [
            message.content
            for message in snapshot.values["messages"]
            if isinstance(message, GraphHumanMessage)
        ] == [expected]


@pytest.mark.asyncio
async def test_tool_context_isolated_across_nested_tasks_and_restored():
    import asyncio
    from uuid import uuid4

    from app.infrastructure.agents._core.user_context import (
        bind_user_context,
        get_user_context,
    )

    original = get_user_context()

    async def read(owner):
        with bind_user_context(UserContext(owner)):

            async def nested():
                await asyncio.sleep(0)
                return get_user_context().user_id

            return await asyncio.create_task(nested())

    other = uuid4()
    assert await asyncio.gather(read(TEST_USER_ID), read(other)) == [
        TEST_USER_ID,
        other,
    ]
    assert get_user_context() == original
