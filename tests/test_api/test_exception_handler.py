import json
from unittest.mock import ANY, MagicMock

import pytest
from fastapi import FastAPI

from app.api.middleware.exception_handler import register_exception_handlers
from app.application.exceptions import (
    AmbiguousTransactionError,
    InvalidTransactionCommandError,
    NoTransactionChangesError,
    TransactionConflictError,
    TransactionNotFoundError,
)
from app.application.ports.logger import Logger
from app.domain.exception.chat_session import (
    ChatSessionAlreadyFinalizedException,
    ChatSessionNotFoundException,
    ChatSessionWriteConflictException,
)
from app.infrastructure.logger import bind_session_context


@pytest.mark.asyncio
async def test_unexpected_exception_is_forwarded_to_logger() -> None:
    app = FastAPI()
    logger = MagicMock(spec=Logger)
    register_exception_handlers(
        app,
        logger=logger,
        session_context_factory=bind_session_context,
    )
    exception = RuntimeError("failure")

    handler = app.exception_handlers[Exception]
    response = await handler(MagicMock(), exception)

    assert response.status_code == 500
    logger.exception.assert_called_once_with(
        "Unhandled error",
        exception=exception,
        details={"user_id": ANY},
    )


@pytest.mark.asyncio
async def test_timeout_is_logged_without_unexpected_exception_traceback() -> None:
    app = FastAPI()
    logger = MagicMock(spec=Logger)
    register_exception_handlers(
        app,
        logger=logger,
        session_context_factory=bind_session_context,
    )
    exception = TimeoutError()

    handler = app.exception_handlers[TimeoutError]
    response = await handler(MagicMock(), exception)

    assert response.status_code == 504
    logger.warning.assert_called_once_with(
        "Request timed out",
        details={"exception_type": "TimeoutError", "user_id": ANY},
    )
    logger.exception.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "handler_type", "status_code"),
    [
        (NoTransactionChangesError(), InvalidTransactionCommandError, 422),
        (TransactionNotFoundError(), TransactionNotFoundError, 404),
        (AmbiguousTransactionError(), TransactionConflictError, 409),
    ],
)
async def test_application_errors_are_translated(
    exception: Exception, handler_type: type[Exception], status_code: int
) -> None:
    app = FastAPI()
    logger = MagicMock(spec=Logger)
    register_exception_handlers(
        app,
        logger=logger,
        session_context_factory=bind_session_context,
    )

    handler = app.exception_handlers[handler_type]
    response = await handler(MagicMock(), exception)
    content = json.loads(response.body)

    assert response.status_code == status_code
    assert content["code"] == exception.code
    assert content["detail"] == exception.public_message
    logger.exception.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "status_code"),
    [
        (ChatSessionNotFoundException("session-123"), 404),
        (ChatSessionAlreadyFinalizedException("session-123"), 409),
        (ChatSessionWriteConflictException("session-123"), 409),
    ],
)
async def test_chat_session_errors_are_translated(
    exception: Exception, status_code: int
) -> None:
    app = FastAPI()
    logger = MagicMock(spec=Logger)
    register_exception_handlers(
        app,
        logger=logger,
        session_context_factory=bind_session_context,
    )

    handler = app.exception_handlers[type(exception)]
    response = await handler(MagicMock(), exception)
    content = json.loads(response.body)

    assert response.status_code == status_code
    assert content["code"] == exception.code
    assert content["detail"] == exception.public_message
    logger.warning.assert_called_once()
    assert logger.warning.call_args.kwargs["details"] == {
        "error_code": exception.code,
        "session_id": "session-123",
    }
    logger.exception.assert_not_called()


@pytest.mark.asyncio
async def test_unexpected_exception_without_session_id_is_still_handled() -> None:
    app = FastAPI()
    logger = MagicMock(spec=Logger)
    register_exception_handlers(
        app,
        logger=logger,
        session_context_factory=bind_session_context,
    )
    exception = RuntimeError("failure")

    handler = app.exception_handlers[Exception]
    response = await handler(MagicMock(), exception)

    assert response.status_code == 500
    logger.exception.assert_called_once_with(
        "Unhandled error",
        exception=exception,
        details={"user_id": ANY},
    )
