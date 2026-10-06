from typing import Awaitable, Callable, Iterator

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain.chat_models import BaseChatModel

from app.application.ports.logger import LoggerFactory
from app.application.ports.observability import TurnRecorder


def _iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    current: BaseException | None = exc
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def is_rate_limit_error(exc: Exception) -> bool:
    return any(
        getattr(current, "code", None) == 429
        or getattr(current, "status_code", None) == 429
        for current in _iter_exception_chain(exc)
    )


class FallbackOn429Middleware(AgentMiddleware):
    def __init__(
        self,
        fallback_llm: BaseChatModel,
        *,
        logger_factory: LoggerFactory,
        recorder: TurnRecorder | None = None,
    ) -> None:
        self._fallback_llm = fallback_llm
        self._logger = logger_factory(__name__)
        self._recorder = recorder

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        try:
            return await handler(request)

        except Exception as e:
            if not is_rate_limit_error(e):
                raise

            self._logger.info(
                "Primary LLM rate limited; activating fallback",
                details={
                    "status_code": 429,
                    "primary_model": type(request.model).__name__,
                    "fallback_model": type(self._fallback_llm).__name__,
                },
            )
            fallback_request = request.override(model=self._fallback_llm)
            if self._recorder is not None:
                try:
                    self._recorder.fallback()
                except Exception:
                    self._logger.warning("Fallback telemetry unavailable")

            return await handler(fallback_request)
