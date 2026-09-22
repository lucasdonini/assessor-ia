from dishka import Provider, Scope, provide

from app.application.ports.logger import (
    InteractionIncrementer,
    LoggerFactory,
    SessionContextFactory,
    TraceContextFactory,
)
from app.infrastructure.logger import (
    bind_session_context,
    bind_trace_context,
    create_logger,
    increment_interaction,
)


class LoggingProvider(Provider):
    scope = Scope.APP

    @provide
    def logger_factory(self) -> LoggerFactory:
        return create_logger

    @provide
    def trace_context_factory(self) -> TraceContextFactory:
        return bind_trace_context

    @provide
    def session_context_factory(self) -> SessionContextFactory:
        return bind_session_context

    @provide
    def interaction_incrementer(self) -> InteractionIncrementer:
        return increment_interaction
