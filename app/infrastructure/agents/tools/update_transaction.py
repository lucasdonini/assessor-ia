from typing import Annotated, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.exceptions import ApplicationError
from app.application.models.transaction_update import (
    UpdateTransactionParams,
)
from app.application.ports.logger import LoggerFactory
from app.infrastructure.agents._core.schemas.tool_response import (
    ToolFailure,
    ToolResponse,
    ToolSuccess,
)
from app.infrastructure.agents._core.user_context import get_user_context
from app.infrastructure.agents.financial.schemas.transaction import TransactionOutput
from app.services.transaction_service import TransactionService


class _UpdateTransactionArgsSchema(BaseModel):
    params: UpdateTransactionParams


class _UpdateTransactionResponse(BaseModel):
    updated: TransactionOutput | None = None


class UpdateTransactionTool(BaseTool):
    name: Literal["update_transaction"] = "update_transaction"
    args_schema: type[BaseModel] = _UpdateTransactionArgsSchema
    description: str = (
        "Atualiza uma transação existente.\n"
        "Estratégias:\n"
        "\t- Se 'id' for informado: atualiza diretamente por ID.\n"
        "\t- Caso contrário: localiza a transação mais recente que combine "
        "(match_text em source_text/description) "
        "E (date_local em America/Sao_Paulo), então atualiza.\n"
        "Retorna o registro atualizado."
    )

    service: Annotated[TransactionService, Field(exclude=True)]
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _run(
        self, params: UpdateTransactionParams
    ) -> ToolResponse[_UpdateTransactionResponse]:
        raise NotImplementedError("This tool only supports asynchronous execution")

    async def _arun(
        self, params: UpdateTransactionParams
    ) -> ToolResponse[_UpdateTransactionResponse]:
        logger = self.logger_factory(__name__)
        logger.debug(
            "Tool called",
            details={
                "tool": self.name,
                "updated_fields": sorted(
                    key
                    for key, value in params.model_dump(exclude={"query"}).items()
                    if value is not None
                ),
                "lookup_fields": sorted(
                    key
                    for key, value in params.query.model_dump().items()
                    if value is not None
                ),
            },
        )
        try:
            updated = await self.service.update_transaction(
                params, user_id=get_user_context().user_id
            )
            logger.debug(
                "Tool succeeded",
                details={"tool": self.name, "updated": True},
            )
            return ToolSuccess(
                data=_UpdateTransactionResponse(
                    updated=TransactionOutput.from_domain(updated)
                )
            )
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
