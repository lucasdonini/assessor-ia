from typing import Annotated, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.exceptions import ApplicationError
from app.application.ports.logger import LoggerFactory
from app.infrastructure.agents._core.schemas.tool_response import (
    ToolFailure,
    ToolResponse,
    ToolSuccess,
)
from app.infrastructure.agents._core.user_context import get_user_context
from app.infrastructure.agents.financial.schemas.transaction import (
    TransactionInput,
    TransactionOutput,
)
from app.services.transaction_service import TransactionService


class _AddTransactionArgsSchema(BaseModel):
    transaction: TransactionInput


class _AddTransactionResponse(BaseModel):
    transaction: TransactionOutput


class AddTransactionTool(BaseTool):
    name: Literal["add_transaction"] = "add_transaction"
    args_schema: type[BaseModel] = _AddTransactionArgsSchema
    description: str = "Insere uma transação financeira no banco de dados PosthreSQL."

    service: Annotated[TransactionService, Field(exclude=True)]
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _run(
        self, transaction: TransactionInput
    ) -> ToolResponse[_AddTransactionResponse]:
        raise NotImplementedError("This tool only supports asynchronous execution")

    async def _arun(
        self, transaction: TransactionInput
    ) -> ToolResponse[_AddTransactionResponse]:
        logger = self.logger_factory(__name__)
        logger.debug(
            "Tool called",
            details={
                "tool": self.name,
                "category": transaction.category.value,
                "transaction_type": transaction.transaction_type.value,
            },
        )
        try:
            added = await self.service.add_transaction(
                transaction.to_domain(user_id=get_user_context().user_id),
                user_id=get_user_context().user_id,
            )
            logger.debug(
                "Tool succeeded",
                details={"tool": self.name, "added": True},
            )
            return ToolSuccess(
                data=_AddTransactionResponse(
                    transaction=TransactionOutput.from_domain(added)
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
