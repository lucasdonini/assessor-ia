from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.application.exceptions import (
    ApplicationError,
    InvalidTransactionCommandError,
    ProfileUnavailableError,
    TransactionConflictError,
    TransactionNotFoundError,
)
from app.application.ports.logger import Logger, SessionContextFactory
from app.domain.exception.chat_session import (
    ChatSessionAlreadyFinalizedException,
    ChatSessionException,
    ChatSessionNotFoundException,
    ChatSessionWriteConflictException,
)


def register_exception_handlers(
    app: FastAPI,
    *,
    logger: Logger,
    session_context_factory: SessionContextFactory,
) -> None:
    def _get_session_id(request: Request) -> str:
        return getattr(request.state, "session_id", "")

    def application_error_response(
        error: ApplicationError,
        status_code: int,
        request: Request,
    ) -> JSONResponse:
        session_id = _get_session_id(request)
        with session_context_factory(session_id):
            logger.warning(
                "Application error",
                details={
                    "error_code": error.code,
                    "status_code": status_code,
                    "user_id": getattr(request.state, "user_id", ""),
                },
            )
            return JSONResponse(
                status_code=status_code,
                content={"code": error.code, "detail": error.public_message},
            )

    @app.exception_handler(InvalidTransactionCommandError)
    async def handle_invalid_transaction_command(
        request: Request, exc: InvalidTransactionCommandError
    ) -> JSONResponse:
        return application_error_response(exc, 422, request)

    @app.exception_handler(TransactionNotFoundError)
    async def handle_transaction_not_found(
        request: Request, exc: TransactionNotFoundError
    ) -> JSONResponse:
        return application_error_response(exc, 404, request)

    @app.exception_handler(TransactionConflictError)
    async def handle_transaction_conflict(
        request: Request, exc: TransactionConflictError
    ) -> JSONResponse:
        return application_error_response(exc, 409, request)

    @app.exception_handler(ProfileUnavailableError)
    async def handle_profile_unavailable(
        request: Request, exc: ProfileUnavailableError
    ) -> JSONResponse:
        return application_error_response(exc, 503, request)

    @app.exception_handler(ApplicationError)
    async def handle_application_error(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        return application_error_response(exc, 400, request)

    @app.exception_handler(TimeoutError)
    async def handle_timeout(request: Request, exc: TimeoutError) -> JSONResponse:
        session_id = _get_session_id(request)
        with session_context_factory(session_id):
            logger.warning(
                "Request timed out",
                details={
                    "exception_type": type(exc).__name__,
                    "user_id": getattr(request.state, "user_id", ""),
                },
            )
            return JSONResponse(
                status_code=504,
                content={
                    "detail": "A operação excedeu o tempo limite. Tente novamente."
                },
            )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        session_id = _get_session_id(request)
        with session_context_factory(session_id):
            logger.exception(
                "Unhandled error",
                exception=exc,
                details={"user_id": getattr(request.state, "user_id", "")},
            )

            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"},
            )

    async def chat_session_exception_response(
        *, status_code: int, log_message: str, exc: ChatSessionException
    ) -> JSONResponse:
        logger.warning(
            log_message,
            details={"error_code": exc.code, "session_id": exc.session_id},
        )
        return JSONResponse(
            status_code=status_code,
            content={"code": exc.code, "detail": exc.public_message},
        )

    @app.exception_handler(ChatSessionNotFoundException)
    async def handle_chat_session_not_found_exception(
        request: Request, exc: ChatSessionNotFoundException
    ) -> JSONResponse:
        return await chat_session_exception_response(
            log_message="User tried to interact with an unexisting session",
            status_code=404,
            exc=exc,
        )

    @app.exception_handler(ChatSessionAlreadyFinalizedException)
    async def handle_chat_session_already_finalized_exception(
        request: Request, exc: ChatSessionAlreadyFinalizedException
    ) -> JSONResponse:
        return await chat_session_exception_response(
            log_message="User tried to interact with an already finalized session",
            status_code=409,
            exc=exc,
        )

    @app.exception_handler(ChatSessionWriteConflictException)
    async def handle_chat_session_write_conflict_exception(
        request: Request, exc: ChatSessionWriteConflictException
    ) -> JSONResponse:
        return await chat_session_exception_response(
            log_message=(
                "Conflict occurred while trying to write a session in database. "
                "Possible concurrency situation."
            ),
            status_code=409,
            exc=exc,
        )
