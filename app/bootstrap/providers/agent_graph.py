from collections.abc import AsyncIterator, Iterator

from dishka import Provider, Scope, provide

from app.application.ports.agent_graph import AgentGraph
from app.application.ports.clock import Clock
from app.application.ports.evidence_validator import EvidenceValidator
from app.application.ports.faq_search import FaqSearch
from app.application.ports.logger import (
    InteractionIncrementer,
    LoggerFactory,
    TraceContextFactory,
)
from app.application.ports.observability import TelemetryReader
from app.application.ports.text_generator import TextGenerator
from app.application.repositories.telemetry_repository import TelemetryRepository
from app.infrastructure.agents import build_agent_graph
from app.infrastructure.config import AgentRuntimeConfig
from app.infrastructure.observability import TurnTelemetry
from app.infrastructure.settings import PydanticSettings
from app.infrastructure.tracing import PrivateTracing
from app.services.chat_history_service import ChatHistoryService
from app.services.event_service import EventService
from app.services.monitor_service import MonitorAccess, MonitorService
from app.services.transaction_service import TransactionService
from app.services.user_profile_service import UserProfileService


class AgentGraphProvider(Provider):
    scope = Scope.APP

    @provide
    def monitor_access(self, settings: PydanticSettings) -> MonitorAccess:
        return MonitorAccess(settings.monitor_operator_emails)

    @provide
    async def telemetry(
        self, logger_factory: LoggerFactory, repository: TelemetryRepository
    ) -> AsyncIterator[TurnTelemetry]:
        telemetry = TurnTelemetry(logger_factory, repository)
        await telemetry.restore()
        try:
            yield telemetry
        finally:
            await telemetry.drain()

    @provide
    def telemetry_reader(self, telemetry: TurnTelemetry) -> TelemetryReader:
        return telemetry

    @provide
    def monitor_service(self, reader: TelemetryReader) -> MonitorService:
        return MonitorService(reader)

    @provide
    def tracing(
        self, settings: PydanticSettings, logger_factory: LoggerFactory
    ) -> Iterator[PrivateTracing]:
        tracing = PrivateTracing(
            enabled=settings.langsmith_tracing,
            api_key=settings.langsmith_api_key.get_secret_value(),
            project=settings.langsmith_project,
            logger_factory=logger_factory,
        )
        yield tracing
        tracing.close()

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
        event_service: EventService,
        telemetry: TurnTelemetry,
        tracing: PrivateTracing,
        validator: EvidenceValidator,
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
            event_service=event_service,
            execution_timeout_seconds=config.execution_timeout_seconds,
            telemetry=telemetry,
            tracing=tracing,
            validator=validator,
        )
