from typing import Any, ClassVar, Sequence, TypedDict, cast

from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph.state import CompiledStateGraph

from app.application.models.currency import known_brl_amount
from app.application.ports.clock import Clock
from app.application.ports.logger import Logger, LoggerFactory
from app.domain.model.transaction import Transaction
from app.infrastructure.agents._core.evidence import (
    current_evidence,
    financial_execution,
)
from app.infrastructure.agents._core.middleware import financial_tool_choice
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
from .schemas.transaction import TransactionOutput


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
        self._write_tool_names = frozenset(
            tools[key].name
            for key in (
                "add_transaction",
                "update_transaction",
                "delete_transaction",
                "restore_transaction",
            )
        )
        self._write_tools = {
            key: tools[key].name
            for key in (
                "add_transaction",
                "update_transaction",
                "delete_transaction",
                "restore_transaction",
            )
        }
        self._clock = clock
        self._agent = agent_factory(
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
        output = self._structured_output(response)
        execution = financial_execution()
        evidence = current_evidence()
        if (
            isinstance(output, FinancialOutput)
            and (
                not output.esclarecer
                or (
                    execution is not None
                    and known_brl_amount(execution.statements) is not None
                )
            )
            and output.intencao.casefold().startswith(
                (
                    "registr",
                    "adicion",
                    "atualiz",
                    "corrig",
                    "cancel",
                    "remov",
                    "delet",
                    "restaur",
                    "lanç",
                    "lanc",
                    "add",
                    "update",
                    "restore",
                )
            )
            and execution is not None
            and not execution.receipts
            and evidence is not None
            and not any(
                item.get("tool") in self._write_tool_names for item in evidence.tools
            )
        ):
            # One bounded generation repair before any write attempt. This never
            # retries a rejected, uncertain or already executed business operation.
            request_state["messages"] = [
                *request_state["messages"],
                AIMessage(content=output.model_dump_json()),
                SystemMessage(
                    content=(
                        "Nenhuma ferramenta de escrita foi chamada nesta solicitação. "
                        "Não afirme sucesso. Se o pedido contém os dados obrigatórios, "
                        "execute a ferramenta financeira correspondente; "
                        "caso contrário, "
                        "preencha esclarecer com o dado obrigatório ausente. Categoria "
                        "e meio de pagamento são opcionais. Não peça confirmação extra."
                    )
                ),
            ]
            intent = output.intencao.casefold()
            tool = (
                "restore_transaction"
                if intent.startswith(("restaur", "restore"))
                else "delete_transaction"
                if intent.startswith(("cancel", "remov", "delet"))
                else "update_transaction"
                if intent.startswith(("atualiz", "corrig", "update"))
                else "add_transaction"
            )
            # Select exactly one real tool on this first attempt; subsequent
            # model calls resume normal structured-output behavior.
            with financial_tool_choice(self._write_tools[tool]):
                response = await self._agent.ainvoke(request_state)  # type: ignore[arg-type]
            output = self._structured_output(response)
        if isinstance(output, FinancialOutput):
            output.escrita = [
                TransactionOutput.from_domain(item).model_dump(mode="json")
                for item in (execution.results.values() if execution else [])
                if isinstance(item, Transaction)
            ] or None
            if (
                execution is not None
                and not execution.receipts
                and not output.esclarecer
                and output.intencao.casefold().startswith(
                    ("registr", "adicion", "lanç", "lanc")
                )
            ):
                output.resposta = "Nenhum lançamento foi registrado nesta solicitação."
            # Native providers may leave AIMessage.content empty and return the
            # actual specialist result only in structured_response.
            response["messages"] = [
                *(response.get("messages") or []),
                AIMessage(content=output.model_dump_json()),
            ]
        last = (response.get("messages") or [None])[-1]
        pending = (
            self.name
            if isinstance(output, FinancialOutput)
            and output.esclarecer
            and not (execution and execution.receipts)
            else ""
        )
        output_length = len(last.content) if last and last.content else 0
        self._logger.info(
            "Agent response",
            details={"from": self.name, "output_length": output_length},
        )
        return {
            GraphStateKeys.MESSAGES: response.get("messages") or [],
            GraphStateKeys.CALLED_AGENTS: [self.name],
            GraphStateKeys.PENDING_ROUTE: pending,
        }

    @staticmethod
    def _structured_output(response: dict[str, Any]) -> FinancialOutput | None:
        structured = response.get("structured_response")
        if isinstance(structured, FinancialOutput):
            return structured
        last = (response.get("messages") or [None])[-1]
        if last:
            try:
                return FinancialOutput.model_validate_json(last.text)
            except ValueError:
                pass
        return None
