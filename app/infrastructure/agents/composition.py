from langgraph.graph import END

from app.application.ports.clock import Clock
from app.application.ports.faq_search import FaqSearch
from app.application.ports.logger import (
    InteractionIncrementer,
    LoggerFactory,
    TraceContextFactory,
)
from app.application.ports.text_generator import TextGenerator
from app.infrastructure.llms import fast_llm, llm_gemini, llm_groq
from app.services.chat_history_service import ChatHistoryService
from app.services.transaction_service import TransactionService
from app.services.user_profile_service import UserProfileService

from ._core.factories.langchain_agent_factory import LangChainAgentFactory
from ._core.middleware import FallbackOn429Middleware
from ._core.specialist import SpecialistRegistration
from .agenda import AgendaAgentNode
from .faq import FAQAgentNode
from .financial import FinancialAgentNode
from .graph import AgentGraphImpl
from .guardrails import InputGuardrailNode, OutputGuardrailNode
from .orquestrator import OrquestratorAgentNode
from .router import RouterAgentNode
from .tools.add_transaction import AddTransactionTool
from .tools.consult_profile import ConsultProfileTool
from .tools.daily_balance import DailyBalanceTool
from .tools.delete_transaction import DeleteTransactionTool
from .tools.faq_rag import FaqRag
from .tools.restore_transaction import RestoreTransactionTool
from .tools.search_history import SearchHistoryTool
from .tools.search_transaction import SearchTransactionsTool
from .tools.total_balance import TotalBalanceTool
from .tools.update_transaction import UpdateTransactionTool


def build_agent_graph(
    *,
    transaction_service: TransactionService,
    profile_service: UserProfileService,
    chat_history_service: ChatHistoryService,
    faq_search: FaqSearch,
    text_generator: TextGenerator,
    logger_factory: LoggerFactory,
    trace_context_factory: TraceContextFactory,
    interaction_incrementer: InteractionIncrementer,
    clock: Clock,
    execution_timeout_seconds: float = 120.0,
) -> AgentGraphImpl:
    specialist_fallback = FallbackOn429Middleware(
        llm_groq,
        logger_factory=logger_factory,
    )

    specialist_factory = LangChainAgentFactory(
        llm=llm_gemini,
        middlewares=(specialist_fallback,),
    )

    support_agent_factory = LangChainAgentFactory(llm=fast_llm)

    total_balance_tool = TotalBalanceTool(
        service=transaction_service,
        logger_factory=logger_factory,
    )

    daily_balance_tool = DailyBalanceTool(
        service=transaction_service,
        logger_factory=logger_factory,
    )

    search_transactions_tool = SearchTransactionsTool(
        service=transaction_service,
        logger_factory=logger_factory,
    )

    add_transaction_tool = AddTransactionTool(
        service=transaction_service,
        logger_factory=logger_factory,
    )

    update_transaction_tool = UpdateTransactionTool(
        service=transaction_service,
        logger_factory=logger_factory,
    )

    delete_transaction_tool = DeleteTransactionTool(
        service=transaction_service,
        logger_factory=logger_factory,
    )

    restore_transaction_tool = RestoreTransactionTool(
        service=transaction_service,
        logger_factory=logger_factory,
    )

    faq_rag = FaqRag(
        faq_search=faq_search,
        logger_factory=logger_factory,
    )

    search_history_tool = SearchHistoryTool(
        service=chat_history_service,
        logger_factory=logger_factory,
    )

    financial = FinancialAgentNode(
        agent_factory=specialist_factory,
        logger_factory=logger_factory,
        clock=clock,
        tools={
            "add_transaction": add_transaction_tool,
            "daily_balance": daily_balance_tool,
            "delete_transaction": delete_transaction_tool,
            "restore_transaction": restore_transaction_tool,
            "search_transactions": search_transactions_tool,
            "total_balance": total_balance_tool,
            "update_transaction": update_transaction_tool,
            "search_history": search_history_tool,
            "consult_profile": ConsultProfileTool(
                service=profile_service, logger_factory=logger_factory
            ),
        },
    )

    agenda = AgendaAgentNode(
        agent_factory=specialist_factory,
        logger_factory=logger_factory,
        clock=clock,
        search_history_tool=search_history_tool,
    )

    faq = FAQAgentNode(
        agent_factory=support_agent_factory,
        logger_factory=logger_factory,
        faq_rag=faq_rag,
    )

    orquestrator = OrquestratorAgentNode(
        agent_factory=support_agent_factory,
        logger_factory=logger_factory,
        clock=clock,
    )

    specialists = (
        SpecialistRegistration(
            node=financial,
            description=(
                "gastos, receitas, dívidas, orçamento, metas, saldo e investimentos"
            ),
            destination=orquestrator.name,
        ),
        SpecialistRegistration(
            node=agenda,
            description=(
                "compromissos, eventos, lembretes, tarefas, horários e conflitos"
            ),
            destination=orquestrator.name,
        ),
        SpecialistRegistration(
            node=faq,
            description=(
                "regras, políticas, termos, privacidade, segurança e comportamento "
                "do sistema"
            ),
            destination=END,
        ),
    )

    router = RouterAgentNode(
        agent_factory=support_agent_factory,
        search_history_tool=search_history_tool,
        logger_factory=logger_factory,
        specialists=specialists,
        clock=clock,
    )

    input_guardrail = InputGuardrailNode(
        text_generator=text_generator,
        approved_route=router.name,
        logger_factory=logger_factory,
    )

    output_guardrail = OutputGuardrailNode(
        text_generator=text_generator,
        logger_factory=logger_factory,
    )

    return AgentGraphImpl(
        input_guardrail=input_guardrail,
        router=router,
        specialists=specialists,
        orquestrator=orquestrator,
        output_guardrail=output_guardrail,
        execution_timeout_seconds=execution_timeout_seconds,
        logger_factory=logger_factory,
        trace_context_factory=trace_context_factory,
        interaction_incrementer=interaction_incrementer,
    )
