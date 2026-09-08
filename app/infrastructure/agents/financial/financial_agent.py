from typing import Any, ClassVar, Sequence, TypedDict, cast

from langchain.tools import BaseTool
from langchain_core.messages import SystemMessage
from langgraph.graph.state import CompiledStateGraph

from app.application.ports.clock import Clock
from app.application.ports.logger import Logger, LoggerFactory
from app.infrastructure.agents._core.prompting.temporal_context import (
    build_temporal_context,
)
from app.infrastructure.agents._core.schemas.specialist_output import FinancialOutput
from app.infrastructure.agents._core.state import GraphState, GraphStateKeys

from .._core.contracts.agent_factory import AgentFactory
from .._core.contracts.agent_node import AgentNode
from ..tools.add_transaction import AddTransactionTool
from ..tools.consult_profile import ConsultProfileTool
from ..tools.daily_balance import DailyBalanceTool
from ..tools.delete_transaction import DeleteTransactionTool
from ..tools.restore_transaction import RestoreTransactionTool
from ..tools.search_history import SearchHistoryTool
from ..tools.search_transaction import SearchTransactionsTool
from ..tools.total_balance import TotalBalanceTool
from ..tools.update_transaction import UpdateTransactionTool
from .financial_prompt import build_financial_prompt


class FinancialAgentTools(TypedDict):
    total_balance: TotalBalanceTool
    daily_balance: DailyBalanceTool
    search_transactions: SearchTransactionsTool
    add_transaction: AddTransactionTool
    update_transaction: UpdateTransactionTool
    delete_transaction: DeleteTransactionTool
    restore_transaction: RestoreTransactionTool
    search_history: SearchHistoryTool
    consult_profile: ConsultProfileTool


class FinancialAgentNode(AgentNode):
    _agent: CompiledStateGraph
    _logger: Logger
    _clock: Clock
    name: ClassVar[str] = "financial"

    def __init__(
        self,
        *,
        agent_factory: AgentFactory,
        logger_factory: LoggerFactory,
        tools: FinancialAgentTools,
        clock: Clock,
    ) -> None:
        prompt = build_financial_prompt(
            total_balance_tool_name=tools["total_balance"].name,
            daily_balance_tool_name=tools["daily_balance"].name,
            search_transactions_tool_name=tools["search_transactions"].name,
            add_transaction_tool_name=tools["add_transaction"].name,
            update_transaction_tool_name=tools["update_transaction"].name,
            delete_transaction_tool_name=tools["delete_transaction"].name,
            restore_transaction_tool_name=tools["restore_transaction"].name,
            search_history_tool_name=tools["search_history"].name,
            consult_profile_tool_name=tools["consult_profile"].name,
        )
        self._logger = logger_factory(__name__)
        self._clock = clock
        self._agent = agent_factory.create(
            system_prompt=prompt,
            tools=cast(Sequence[BaseTool], tools.values()),
            response_format=FinancialOutput,
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
        response = await self._agent.ainvoke(request_state)  # type: ignore[arg-type]
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
