from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.infrastructure.agents._core.contracts.agent_factory import AgentFactory
from app.infrastructure.agents._core.contracts.agent_node import AgentNode
from app.infrastructure.agents._core.specialist import SpecialistRegistration
from app.infrastructure.agents.router.router_agent import RouterAgentNode
from app.infrastructure.agents.tools.search_history import SearchHistoryTool
from app.infrastructure.clock import FixedClock
from app.services.chat_history_service import ChatHistoryService


@pytest.fixture
def router(mock_logger_factory: MagicMock) -> RouterAgentNode:
    specialist = MagicMock(spec=AgentNode)
    specialist.name = "financial"
    history_tool = SearchHistoryTool(
        service=MagicMock(spec=ChatHistoryService),
        logger_factory=mock_logger_factory,
    )
    return RouterAgentNode(
        agent_factory=create_autospec(AgentFactory, instance=True),
        search_history_tool=history_tool,
        logger_factory=mock_logger_factory,
        specialists=(
            SpecialistRegistration(
                node=specialist, description="Finanças", destination="end"
            ),
        ),
        clock=FixedClock(
            datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc),
            "America/Sao_Paulo",
        ),
    )


def test_router_registers_complete_tool_name(router: RouterAgentNode) -> None:
    assert router._allowed_tool_names == frozenset({"search_history"})


@pytest.mark.asyncio
async def test_structured_route_is_not_inferred_from_native_json_text(router):
    human = HumanMessage(content="Comprei um livro por 42 reais")
    router._agent = AsyncMock()
    router._agent.ainvoke.return_value = {
        "structured_response": {"route": "financial", "response": ""},
        "messages": [human, AIMessage(content='{"route":"financial","response":""}')],
    }
    result = await router(
        {"messages": [human], "route": "router", "called_agents": [], "pii_map": {}}
    )
    assert result["route"] == "financial"
    assert result["messages"][-1].content == (
        "ROUTE=financial\nPERGUNTA_ORIGINAL=Comprei um livro por 42 reais"
    )
    assert not any('"route"' in msg.text for msg in result["messages"])


@pytest.mark.asyncio
async def test_unstructured_or_unknown_route_cannot_become_a_user_reply(router):
    router._agent = AsyncMock()
    state = {
        "messages": [HumanMessage(content="Relato fictício")],
        "route": "router",
        "called_agents": [],
        "pii_map": {},
    }
    for response in [
        {"messages": [AIMessage(content="Compra registrada!")]},
        {"structured_response": {"route": "unknown", "response": ""}},
    ]:
        router._agent.ainvoke.return_value = response
        with pytest.raises(ValueError):
            await router(state)


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", ["Sim", "120", "ok"])
async def test_pending_specialist_owns_short_confirmation_without_reclassification(
    router, reply
):
    router._agent = AsyncMock()
    result = await router(
        {
            "messages": [HumanMessage(content=reply)],
            "route": "router",
            "pending_route": "financial",
            "called_agents": [],
            "pii_map": {},
        }
    )
    assert result["route"] == "financial"
    assert result["pending_route"] == ""
    router._agent.ainvoke.assert_not_awaited()


class TestIsSpecialistJson:
    def test_valid_json_with_dominio(self, router: RouterAgentNode) -> None:
        assert (
            router._is_specialist_json('{"dominio": "financeiro", "resposta": "ok"}')
            is True
        )

    def test_valid_json_with_dominio_agenda(self, router: RouterAgentNode) -> None:
        assert router._is_specialist_json('{"dominio": "agenda"}') is True

    def test_valid_json_without_dominio(self, router: RouterAgentNode) -> None:
        assert router._is_specialist_json('{"outro": "valor"}') is False

    def test_not_json_string(self, router: RouterAgentNode) -> None:
        assert router._is_specialist_json("hello world") is False

    def test_not_string_int(self, router: RouterAgentNode) -> None:
        assert router._is_specialist_json(123) is False

    def test_not_string_none(self, router: RouterAgentNode) -> None:
        assert router._is_specialist_json(None) is False

    def test_not_string_dict(self, router: RouterAgentNode) -> None:
        assert router._is_specialist_json({"dominio": "teste"}) is False

    def test_malformed_json(self, router: RouterAgentNode) -> None:
        assert router._is_specialist_json("{dominio:}") is False

    def test_empty_dict(self, router: RouterAgentNode) -> None:
        assert router._is_specialist_json("{}") is False

    def test_whitespace_prefix_suffix(self, router: RouterAgentNode) -> None:
        assert router._is_specialist_json('  {"dominio": "agenda"}  ') is True


class TestFilterMessagesForRouter:
    def test_filters_out_foreign_tool_calls(self, router: RouterAgentNode) -> None:
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "total_balance", "args": {}, "id": "call_tb"},
            ],
        )
        result = router._filter_messages_for_router([msg])
        assert len(result) == 0

    def test_keeps_own_tool_calls(self, router: RouterAgentNode) -> None:
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "search_history", "args": {"search": "test"}, "id": "call_sh"},
            ],
        )
        result = router._filter_messages_for_router([msg])
        assert len(result) == 1

    def test_filters_specialist_json_aimessage(self, router: RouterAgentNode) -> None:
        msg = AIMessage(content='{"dominio": "financeiro", "resposta": "saldo ok"}')
        result = router._filter_messages_for_router([msg])
        assert len(result) == 0

    def test_keeps_non_specialist_aimessage(self, router: RouterAgentNode) -> None:
        msg = AIMessage(content="Olá, como posso ajudar?")
        result = router._filter_messages_for_router([msg])
        assert len(result) == 1
        assert result[0].content == "Olá, como posso ajudar?"

    def test_filters_toolmessage_for_foreign_tool(
        self, router: RouterAgentNode
    ) -> None:
        msgs = [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "total_balance", "args": {}, "id": "call_tb"},
                ],
            ),
            ToolMessage(content="5000", tool_call_id="call_tb"),
        ]
        result = router._filter_messages_for_router(msgs)
        assert len(result) == 0

    def test_keeps_toolmessage_for_own_tool(self, router: RouterAgentNode) -> None:
        msg = ToolMessage(content='[{"summary": "teste"}]', tool_call_id="call_sh")
        result = router._filter_messages_for_router([msg])
        assert len(result) == 1

    def test_removes_foreign_calls_but_keeps_own_mixed(
        self, router: RouterAgentNode
    ) -> None:
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "total_balance", "args": {}, "id": "call_tb"},
                {"name": "search_history", "args": {"search": "test"}, "id": "call_sh"},
            ],
        )
        result = router._filter_messages_for_router([msg])
        assert len(result) == 1
        assert len(result[0].tool_calls) == 1
        assert result[0].tool_calls[0]["name"] == "search_history"

    def test_keeps_human_message(self, router: RouterAgentNode) -> None:
        msg = HumanMessage(content="Qual meu saldo?")
        result = router._filter_messages_for_router([msg])
        assert len(result) == 1

    def test_foreign_tool_call_without_id_is_ignored(
        self, router: RouterAgentNode
    ) -> None:
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "total_balance", "args": {}, "id": None},
            ],
        )
        result = router._filter_messages_for_router([msg])
        assert len(result) == 0

    def test_complex_scenario(self, router: RouterAgentNode) -> None:
        msgs = [
            HumanMessage(content="Qual meu saldo?"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "total_balance", "args": {}, "id": "call_tb"},
                ],
            ),
            ToolMessage(content="5000", tool_call_id="call_tb"),
            AIMessage(content='{"dominio": "financeiro", "resposta": "R$ 5000"}'),
        ]
        result = router._filter_messages_for_router(msgs)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
