import asyncio
from contextlib import nullcontext
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from app.application.models.evidence import SAFE_REPLY, Judgment
from app.application.models.user_context import UserContext
from app.domain.model.chat_entry import HumanMessage
from app.infrastructure.agents._core.contracts.agent_node import AgentNode
from app.infrastructure.agents._core.evidence import (
    current_evidence,
    evidence_execution,
    record_tool,
)
from app.infrastructure.agents._core.schemas.tool_response import ToolFailure
from app.infrastructure.agents._core.specialist import SpecialistRegistration
from app.infrastructure.agents.evidence_judge import EvidenceJudgeNode
from app.infrastructure.agents.graph import AgentGraphImpl
from app.infrastructure.agents.tools.agenda import agenda_execution


@pytest.mark.asyncio
@pytest.mark.parametrize("approved", [True, False])
async def test_exact_candidate_or_safe_message(approved):
    validator = AsyncMock()
    validator.validate.return_value = Judgment(approved=approved, reason="test")
    candidate = "  Você gastou R$ 120,00.\n"
    with evidence_execution(uuid4(), ("Quanto gastei?",)), agenda_execution():
        result = await EvidenceJudgeNode(validator)(
            {"messages": [AIMessage(content=candidate)]}
        )
    assert result["messages"][0].content == (candidate if approved else SAFE_REPLY)
    assert result["called_agents"] == ["evidence_judge"]


@pytest.mark.asyncio
async def test_receipt_does_not_depend_on_post_commit_judge():
    validator = AsyncMock()
    validator.validate.side_effect = RuntimeError("down")
    with evidence_execution(uuid4(), ("120 reais",)) as evidence, agenda_execution():
        evidence.financial.receipts.append("Lançamento registrado em BRL.")
        result = await EvidenceJudgeNode(validator)(
            {"messages": [AIMessage(content="invented")]}
        )
    assert result["messages"][0].content == "Lançamento registrado em BRL."
    validator.validate.assert_not_awaited()


@pytest.mark.asyncio
async def test_parallel_invocations_and_reset():
    async def turn(name):
        with evidence_execution(uuid4(), (name,)) as evidence:
            await asyncio.sleep(0)
            record_tool(name, {"query": name}, ToolFailure.unexpected_error())
            await asyncio.sleep(0)
            assert evidence.tools[0]["tool"] == name
            assert len(evidence.tools) == 1

    await asyncio.gather(turn("first"), turn("second"))
    assert current_evidence() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["financial", "agenda", "faq", "direct", "blocked"])
async def test_all_graph_exits_are_judged_once(route):
    order = []

    class Node(AgentNode):
        def __init__(self, name, content):
            self.name = name
            self.content = content

        async def __call__(self, state):
            order.append(self.name)
            if self.name == "input_guardrail":
                return {
                    "route": "__end__" if route == "blocked" else "router",
                    "messages": [AIMessage(content="Bloqueado")]
                    if route == "blocked"
                    else [],
                    "called_agents": [self.name],
                }
            return {
                "messages": [AIMessage(content=self.content)],
                "called_agents": [self.name],
            }

    validator = AsyncMock()
    validator.validate.return_value = Judgment(approved=True, reason="approved")
    graph = AgentGraphImpl(
        input_guardrail=Node("input_guardrail", ""),
        router=Node("router", "Olá" if route == "direct" else f"ROUTE={route}"),
        specialists=[
            SpecialistRegistration(
                Node(name, "candidate"),
                name,
                "__end__" if name == "faq" else "orquestrator",
            )
            for name in ("financial", "agenda", "faq")
        ],
        orquestrator=Node("orquestrator", "orchestrated"),
        output_guardrail=Node("output_guardrail", "compliance revised"),
        evidence_judge=EvidenceJudgeNode(validator),
        execution_timeout_seconds=5,
        logger_factory=lambda _: MagicMock(),
        trace_context_factory=lambda _: nullcontext(),
        interaction_incrementer=lambda: 1,
    )
    result = await graph.execute_agent_flux(
        HumanMessage(content="Pergunta"), "session", context=UserContext(uuid4())
    )
    if route == "blocked":
        validator.validate.assert_not_awaited()
        assert result.called_agents == ("input_guardrail",)
    else:
        validator.validate.assert_awaited_once()
        assert result.called_agents[-1] == "evidence_judge"
        expected = (
            "compliance revised"
            if route in {"financial", "agenda"}
            else "Olá"
            if route == "direct"
            else "candidate"
        )
        assert (
            validator.validate.call_args.args[0].candidate
            == result.message.content
            == expected
        )
