from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.ports.logger import Logger
from app.infrastructure.agents._core.middleware import (
    FallbackOn429Middleware,
    is_rate_limit_error,
)


class _StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")


class _CodeError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"HTTP {code}")


def _wrap_exception(cause: Exception) -> Exception:
    try:
        raise cause
    except Exception as exc:
        try:
            raise RuntimeError("LLM adapter error") from exc
        except RuntimeError as wrapper:
            return wrapper


def test_detects_direct_rate_limit_error() -> None:
    assert is_rate_limit_error(_StatusError(429)) is True


def test_detects_rate_limit_in_wrapped_cause() -> None:
    wrapped = _wrap_exception(_CodeError(429))

    assert is_rate_limit_error(wrapped) is True


def test_ignores_non_rate_limit_in_wrapped_cause() -> None:
    wrapped = _wrap_exception(_CodeError(409))

    assert is_rate_limit_error(wrapped) is False


def test_exception_chain_handles_cycles() -> None:
    error = RuntimeError("cycle")
    error.__cause__ = error

    assert is_rate_limit_error(error) is False


@pytest.mark.asyncio
async def test_middleware_uses_fallback_for_wrapped_rate_limit() -> None:
    fallback_llm = MagicMock()
    middleware = FallbackOn429Middleware(
        fallback_llm,
        logger_factory=lambda _: MagicMock(spec=Logger),
    )
    request = MagicMock()
    fallback_request = MagicMock()
    request.override.return_value = fallback_request
    expected_response = MagicMock()
    handler = AsyncMock(
        side_effect=[
            _wrap_exception(_CodeError(429)),
            expected_response,
        ]
    )

    response = await middleware.awrap_model_call(request, handler)

    assert response is expected_response
    request.override.assert_called_once_with(model=fallback_llm)
    assert handler.await_args_list[0].args == (request,)
    assert handler.await_args_list[1].args == (fallback_request,)


@pytest.mark.asyncio
async def test_middleware_logs_fallback_activation() -> None:
    fallback_llm = MagicMock()
    logger = MagicMock(spec=Logger)
    middleware = FallbackOn429Middleware(
        fallback_llm,
        logger_factory=lambda _: logger,
    )
    request = MagicMock()
    request.override.return_value = MagicMock()
    handler = AsyncMock(
        side_effect=[
            _wrap_exception(_CodeError(429)),
            MagicMock(),
        ]
    )

    await middleware.awrap_model_call(request, handler)

    logger.info.assert_called_once_with(
        "Primary LLM rate limited; activating fallback",
        details={
            "status_code": 429,
            "primary_model": "MagicMock",
            "fallback_model": "MagicMock",
        },
    )


@pytest.mark.asyncio
async def test_middleware_reraises_non_rate_limit_error() -> None:
    middleware = FallbackOn429Middleware(
        MagicMock(),
        logger_factory=lambda _: MagicMock(spec=Logger),
    )
    request = MagicMock()
    wrapped = _wrap_exception(_CodeError(409))
    handler = AsyncMock(side_effect=wrapped)

    with pytest.raises(RuntimeError, match="LLM adapter error"):
        await middleware.awrap_model_call(request, handler)

    request.override.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_activation_is_recorded_once_for_actual_middleware():
    from app.infrastructure.observability import TurnTelemetry

    store = TurnTelemetry(lambda _: MagicMock())
    middleware = FallbackOn429Middleware(
        MagicMock(), logger_factory=lambda _: MagicMock()
    )
    error = RuntimeError("rate limited")
    error.status_code = 429
    handler = AsyncMock(side_effect=[error, MagicMock()])
    with store.turn("turn", "owner", "session"):
        await middleware.awrap_model_call(MagicMock(), handler)
    assert store.snapshot().turns[0].fallbacks == 1
    assert store.snapshot().turns[0].status == "ok"
