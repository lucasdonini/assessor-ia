from dishka import Provider, Scope, provide

from app.application.ports.agent_graph import AgentGraph
from app.application.ports.clock import Clock
from app.application.ports.faq_search import FaqSearch
from app.application.ports.logger import (
    InteractionIncrementer,
    LoggerFactory,
    TraceContextFactory,
)
from app.application.ports.text_generator import TextGenerator
from app.infrastructure.agents import build_agent_graph
from app.infrastructure.config import AgentRuntimeConfig
from app.services.chat_history_service import ChatHistoryService
from app.services.transaction_service import TransactionService
from app.services.user_profile_service import UserProfileService


class AgentGraphProvider(Provider):
    scope = Scope.APP

    @provide
    def graph(
        self,
        transaction_service: TransactionService,
        profile_service: UserProfileService,
        chat_history_service: ChatHistoryService,
        faq_search: FaqSearch,
        text_generator: TextGenerator,
        logger_factory: LoggerFactory,
        trace_context_factory: TraceContextFactory,
        interaction_incrementer: InteractionIncrementer,
        clock: Clock,
        config: AgentRuntimeConfig,
    ) -> AgentGraph:
        return build_agent_graph(
            transaction_service=transaction_service,
            profile_service=profile_service,
            chat_history_service=chat_history_service,
            faq_search=faq_search,
            text_generator=text_generator,
            logger_factory=logger_factory,
            trace_context_factory=trace_context_factory,
            interaction_incrementer=interaction_incrementer,
            clock=clock,
            execution_timeout_seconds=config.execution_timeout_seconds,
        )
