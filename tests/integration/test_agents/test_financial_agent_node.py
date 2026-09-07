from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.application.models.transaction_query import TransactionQueryParams
from app.infrastructure.agents._core.schemas.specialist_output import FinancialOutput
from app.infrastructure.agents._core.state import GraphState, GraphStateKeys
from app.infrastructure.agents.financial import FinancialAgentNode
from app.services.transaction_service import TransactionService
from tests.user_identity import TEST_USER_ID

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("apply_migrations", "seed_transactions"),
]


async def _run_node(node: FinancialAgentNode) -> dict[GraphStateKeys, Any]:
    return await node(
        GraphState(
            messages=[
                HumanMessage(content="Consulte os dados financeiros solicitados.")
            ],
            called_agents=[],
            route="financial",
            pii_map={},
        )
    )


def _tool_result(result: dict[GraphStateKeys, Any], call_id: str) -> ToolMessage:
    messages = [
        message
        for message in result["messages"]
        if isinstance(message, ToolMessage) and message.tool_call_id == call_id
    ]
    assert len(messages) == 1
    assert messages[0].status == "success"
    return messages[0]


def _structured_response() -> AIMessage:
    return AIMessage(
        content=FinancialOutput(
            intencao="consultar", resposta="Consulta concluída."
        ).model_dump_json()
    )


@pytest.mark.parametrize(
    ("tool_name", "args", "expected_text"),
    [
        ("total_balance", {}, "7600.0"),
        ("daily_balance", {"target_date": "2026-06-01"}, "4850.0"),
        (
            "search_transactions",
            {"params": {"category": "comida", "limit": 10}},
            "Almoço",
        ),
    ],
)
async def test_calls_financial_read_tool(
    financial_agent_node: FinancialAgentNode,
    mock_gemini_ainvoke: AsyncMock,
    tool_name: str,
    args: dict[str, Any],
    expected_text: str,
) -> None:
    mock_gemini_ainvoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{"name": tool_name, "args": args, "id": "call_read"}],
        ),
        _structured_response(),
    ]

    result = await _run_node(financial_agent_node)

    assert financial_agent_node.name in result["called_agents"]
    output = _tool_result(result, "call_read").text
    assert expected_text in output
    if tool_name == "search_transactions":
        assert "Uber" not in output
    assert mock_gemini_ainvoke.await_count == 2


async def test_calls_add_tool_and_persists_transaction(
    financial_agent_node: FinancialAgentNode,
    mock_gemini_ainvoke: AsyncMock,
    transaction_service: TransactionService,
) -> None:
    mock_gemini_ainvoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "add_transaction",
                    "args": {
                        "transaction": {
                            "amount": 100.0,
                            "category": "comida",
                            "transaction_type": "EXPENSE",
                            "source_text": "novo almoço pelo agente",
                        }
                    },
                    "id": "call_add",
                }
            ],
        ),
        _structured_response(),
    ]

    result = await _run_node(financial_agent_node)

    _tool_result(result, "call_add")
    persisted = await transaction_service.search_transactions(
        TransactionQueryParams(source_text="novo almoço pelo agente"),
        user_id=TEST_USER_ID,
    )
    assert len(persisted) == 1
    assert persisted[0].amount == 100.0
    assert mock_gemini_ainvoke.await_count == 2


async def test_direct_clarification_without_tool_call(
    financial_agent_node: FinancialAgentNode,
    mock_gemini_ainvoke: AsyncMock,
) -> None:
    expected = FinancialOutput(
        intencao="esclarecer",
        resposta="Preciso saber qual período consultar.",
        esclarecer="Qual período deseja consultar?",
    )
    mock_gemini_ainvoke.return_value = AIMessage(content=expected.model_dump_json())

    result = await _run_node(financial_agent_node)

    assert result["messages"][-1].text == expected.model_dump_json()
    assert not any(isinstance(message, ToolMessage) for message in result["messages"])
    mock_gemini_ainvoke.assert_awaited_once()
