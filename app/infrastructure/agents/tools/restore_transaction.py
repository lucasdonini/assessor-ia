from typing import Annotated, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.exceptions import ApplicationError
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.application.ports.logger import LoggerFactory
from app.infrastructure.agents._core.user_context import get_user_context
from app.infrastructure.agents.financial.schemas.tool_response import (
    ToolFailure,
    ToolResponse,
    ToolSuccess,
)
from app.services.transaction_service import TransactionService


class _RestoreTransactionArgsSchema(BaseModel):
    query: UpdateTransactionQuery


class _RestoreTransactionResponse(BaseModel):
    restored: bool


class RestoreTransactionTool(BaseTool):
    name: Literal["restore_transaction"] = "restore_transaction"
    args_schema: type[BaseModel] = _RestoreTransactionArgsSchema
    description: str = (
        "Restaura uma transação deletada / cancelada.\n"
        "Estratégias:\n"
        "\t- Se 'id' for informado: restaura diretamente por ID.\n"
        "\t- Caso contrário: localiza a transação mais recente que combine "
        "(match_text em source_text/description) "
        "E (date_local em America/Sao_Paulo), então restaura.\n"
        "Retorna verdadeiro se restaurou algo, falso caso contrário"
    )

    service: Annotated[TransactionService, Field(exclude=True)]
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _run(
        self, query: UpdateTransactionQuery
    ) -> ToolResponse[_RestoreTransactionResponse]:
        raise NotImplementedError("This tool only supports asynchronous execution")

    async def _arun(
        self, query: UpdateTransactionQuery
    ) -> ToolResponse[_RestoreTransactionResponse]:
        logger = self.logger_factory(__name__)
        logger.debug(
            "Tool called",
            details={
                "tool": self.name,
                "lookup_fields": sorted(
                    key
                    for key, value in query.model_dump().items()
                    if value is not None
                ),
            },
        )
        params = UpdateTransactionParams(query=query, is_canceled=False)
        response: _RestoreTransactionResponse
        try:
            await self.service.update_transaction(
                params, user_id=get_user_context().user_id
            )
            logger.debug(
                "Tool succeeded",
                details={"tool": self.name, "restored": True},
            )
            response = _RestoreTransactionResponse(restored=True)
            return ToolSuccess(data=response)
        except ApplicationError as e:
            logger.warning(
                "Tool rejected operation",
                details={"tool": self.name, "error_code": e.code},
            )
            return ToolFailure.application_error(e)
        except Exception as e:
            logger.exception(
                "Tool failed",
                exception=e,
                details={"tool": self.name},
            )
            return ToolFailure.unexpected_error()
