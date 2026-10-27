from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.infrastructure.agents._core.evidence import evidence_execution
from app.infrastructure.agents._core.schemas.specialist_output import FinancialOutput
from app.infrastructure.agents.financial.financial_agent import FinancialAgentNode
from app.infrastructure.clock import FixedClock


def node_for(*outputs):
    node = FinancialAgentNode.__new__(FinancialAgentNode)
    node._logger = MagicMock()
    node._clock = FixedClock(
        datetime(2026, 10, 27, 12, tzinfo=timezone.utc), "America/Sao_Paulo"
    )
    node._write_tool_names = frozenset({"add_transaction"})
    node._write_tools = {"add_transaction": "add_transaction"}
    node._agent = AsyncMock()
    node._agent.ainvoke.side_effect = [
        {"messages": [AIMessage(content="")], "structured_response": output}
        for output in outputs
    ]
    return node


def state():
    return {
        "messages": [HumanMessage(content="Uma compra fictícia")],
        "route": "financial",
        "pii_map": {},
        "called_agents": [],
    }


@pytest.mark.asyncio
async def test_native_clarification_is_forwarded_and_keeps_pending_domain():
    output = FinancialOutput(
        intencao="registrar",
        resposta="Falta o valor.",
        esclarecer="Qual foi o valor em BRL?",
    )
    node = node_for(output)
    with evidence_execution(uuid4(), ("Uma compra fictícia",)):
        result = await node(state())
    forwarded = FinancialOutput.model_validate_json(result["messages"][-1].text)
    assert forwarded.esclarecer == output.esclarecer
    assert result["pending_route"] == "financial"
    node._agent.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_one_generation_repair_when_model_claims_write_without_any_tool_attempt():
    node = node_for(
        FinancialOutput(intencao="registrar", resposta="Registrei!"),
        FinancialOutput(
            intencao="registrar", resposta="Falta o valor.", esclarecer="Qual valor?"
        ),
    )
    with evidence_execution(uuid4(), ("Uma compra fictícia",)):
        result = await node(state())
    assert node._agent.ainvoke.await_count == 2
    assert "Qual valor?" in result["messages"][-1].text


@pytest.mark.asyncio
async def test_failed_tool_attempt_never_triggers_another_write_generation():
    node = node_for(FinancialOutput(intencao="registrar", resposta="Registrei!"))
    with evidence_execution(uuid4(), ("Uma compra fictícia",)) as evidence:
        evidence.tools.append(
            {"tool": "add_transaction", "result": {"status": "error"}}
        )
        result = await node(state())
    node._agent.ainvoke.assert_awaited_once()
    output = FinancialOutput.model_validate_json(result["messages"][-1].text)
    assert output.escrita is None
    assert "Nenhum lançamento" in output.resposta
