import asyncio
from contextlib import nullcontext
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage as GraphHumanMessage
from langgraph.graph import END

from app.application.models.user_context import UserContext
from app.application.ports.logger import Logger
from app.domain.model.chat_entry import AssistantMessage, HumanMessage
from app.infrastructure.agents._core.contracts.agent_node import AgentNode
from app.infrastructure.agents._core.evidence import current_evidence
from app.infrastructure.agents._core.specialist import SpecialistRegistration
from app.infrastructure.agents._core.state import GraphState, GraphStateKeys
from app.infrastructure.agents.evidence_judge import EvidenceJudgeNode
from app.infrastructure.agents.graph import AgentGraphImpl
from app.infrastructure.observability import observe_block
from tests.user_identity import TEST_USER_ID


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["exception", "timeout"])
async def test_confirmed_receipt_survives_later_generation_failure(graph, failure):
    class ConfirmedWrite(AgentNode):
        name = "financial"

        async def __call__(self, state):
            evidence = current_evidence()
            assert evidence is not None
            evidence.financial.receipts.append("Lançamento registrado em BRL.")
            evidence.financial.outcomes.append("confirmed")
            if failure == "timeout":
                await asyncio.sleep(3)
            raise RuntimeError("generation failed after confirmed write")

    validator = AsyncMock()
    validator.validate.side_effect = RuntimeError("judge unavailable after commit")
    subject = AgentGraphImpl(
        input_guardrail=graph._input_guardrail,
        router=graph._router,
        specialists=[
            SpecialistRegistration(ConfirmedWrite(), "financial", "orquestrator")
        ],
        orquestrator=graph._orquestrator,
        output_guardrail=graph._output_guardrail,
        evidence_judge=EvidenceJudgeNode(validator),
        execution_timeout_seconds=2,
        logger_factory=lambda _: MagicMock(spec=Logger),
        trace_context_factory=lambda _: nullcontext(),
        interaction_incrementer=lambda: 1,
    )
    result = await subject.execute_agent_flux(
        HumanMessage(content="financial"), "session", context=UserContext(TEST_USER_ID)
    )
    assert result.message.content == "Lançamento registrado em BRL."
    validator.validate.assert_not_awaited()
    assert subject._telemetry.snapshot().turns[0].status == "ok"


class _InputGuardrail(AgentNode):
    name: ClassVar[str] = "input_guardrail"

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        blocked = state["messages"][-1].content == "blocked"
        result: dict[GraphStateKeys, Any] = {
            GraphStateKeys.CALLED_AGENTS: [self.name],
            GraphStateKeys.ROUTE: END if blocked else "router",
        }
        if blocked:
            observe_block("prompt_injection")
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
    assert graph._telemetry.snapshot().turns[0].route == "financial"
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
    assert graph._telemetry.snapshot().turns[-1].status == "blocked"

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


@pytest.mark.asyncio
async def test_nested_runnable_models_inherit_turn_and_node(graph, monkeypatch):
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.runnables import RunnableLambda

    from app.infrastructure.text_generator import LLMTextGenerator

    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="synthetic",
                usage_metadata={
                    "input_tokens": 7,
                    "output_tokens": 3,
                    "total_tokens": 10,
                },
            )
        ]
    )
    generator = LLMTextGenerator(model)

    async def nested(state):
        await generator.generate("PRIVATE_SENTINEL")
        return await model.ainvoke("PRIVATE_SENTINEL")

    nested_runnable = RunnableLambda(nested)
    original = _InputGuardrail.__call__

    async def guard(self, state):
        await nested_runnable.ainvoke(state)
        return await original(self, state)

    monkeypatch.setattr(_InputGuardrail, "__call__", guard)
    await graph.execute_agent_flux(
        HumanMessage(content="financial"), "nested", context=UserContext(TEST_USER_ID)
    )
    turn = graph._telemetry.snapshot().turns[0]
    assert len(turn.calls) == 2
    assert all(call.node == "input_guardrail" for call in turn.calls)
    assert sum(call.input_tokens for call in turn.calls) == 14
    assert "PRIVATE_SENTINEL" not in turn.model_dump_json()
    await generator.generate("outside turn")
    assert len(graph._telemetry.snapshot().turns[0].calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [TimeoutError, ValueError])
async def test_failed_graph_closes_turn_with_original_exception(graph, failure):
    from unittest.mock import AsyncMock

    graph._agent_flux = AsyncMock()
    graph._agent_flux.ainvoke.side_effect = failure("synthetic failure")
    with pytest.raises(failure, match="synthetic failure"):
        await graph.execute_agent_flux(
            HumanMessage(content="financial"),
            "failure",
            context=UserContext(TEST_USER_ID),
        )
    snapshot = graph._telemetry.snapshot()
    assert snapshot.in_progress == 0
    assert len(snapshot.turns) == 1
    assert snapshot.turns[0].status == "error"


@pytest.mark.asyncio
async def test_graph_task_cancellation_closes_active_turn(graph):
    import asyncio
    from unittest.mock import AsyncMock

    started = asyncio.Event()

    async def wait(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    graph._agent_flux = AsyncMock()
    graph._agent_flux.ainvoke.side_effect = wait
    task = asyncio.create_task(
        graph.execute_agent_flux(
            HumanMessage(content="financial"),
            "cancel",
            context=UserContext(TEST_USER_ID),
        )
    )
    await started.wait()
    assert graph._telemetry.snapshot().in_progress == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert graph._telemetry.snapshot().in_progress == 0
    assert graph._telemetry.snapshot().turns[0].status == "cancelled"


@pytest.mark.asyncio
async def test_metadata_traces_reach_outbound_boundary_without_content(
    graph, monkeypatch
):
    import asyncio
    import json

    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langsmith import Client
    from langsmith.schemas import LangSmithInfo

    from app.infrastructure.tracing import PrivateTracing

    sent = []

    def capture(self, run, **kwargs):
        sent.append(run)

    monkeypatch.setattr(Client, "_create_run", capture)
    monkeypatch.setattr(Client, "_update_run", capture)
    monkeypatch.setattr(
        "app.infrastructure.tracing.Client",
        lambda **kwargs: Client(
            **kwargs, info=LangSmithInfo(), api_url="https://synthetic.invalid"
        ),
    )
    graph._tracing = PrivateTracing(
        enabled=True,
        api_key="synthetic-key",
        project="synthetic",
        logger_factory=lambda _: MagicMock(),
    )
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="PRIVATE_SENTINEL",
                usage_metadata={
                    "input_tokens": 7,
                    "output_tokens": 3,
                    "total_tokens": 10,
                },
            )
        ]
    )
    original = _InputGuardrail.__call__

    async def guard(self, state):
        await model.ainvoke("PRIVATE_SENTINEL")
        return await original(self, state)

    monkeypatch.setattr(_InputGuardrail, "__call__", guard)
    await graph.execute_agent_flux(
        HumanMessage(content="financial"),
        "private-trace",
        context=UserContext(TEST_USER_ID),
    )
    await asyncio.to_thread(graph._tracing.close)
    assert sent
    assert "PRIVATE_SENTINEL" not in json.dumps(sent, default=str)
    turn = graph._telemetry.snapshot().turns[0]
    assert any(str(run.get("id")) == turn.turn_id for run in sent)
    assert any(run.get("parent_run_id") is not None for run in sent)
    assert any(
        run.get("extra", {})
        .get("metadata", {})
        .get("usage_metadata", {})
        .get("input_tokens")
        == 7
        for run in sent
    )
