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
from app.services.transaction_service import TransactionService


class _TotalBalanceArgsSchema(BaseModel):
    pass


class _TotalBalanceResponse(BaseModel):
    balance: float


class TotalBalanceTool(BaseTool):
    name: Literal["total_balance"] = "total_balance"
    args_schema: type[BaseModel] = _TotalBalanceArgsSchema
    description: str = (
        "Recupera do banco de dados o saldo atual "
        "a partir de todas as transações registradas"
    )

    service: Annotated[TransactionService, Field(exclude=True)]
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _run(self) -> ToolResponse[_TotalBalanceResponse]:
        raise NotImplementedError("This tool only supports asynchronous execution")

    async def _arun(self) -> ToolResponse[_TotalBalanceResponse]:
        logger = self.logger_factory(__name__)
        logger.debug(
            "Tool called",
            details={"tool": self.name},
        )
        try:
            balance = await self.service.calculate_total_balance(
                user_id=get_user_context().user_id
            )
            logger.debug(
                "Tool succeeded",
                details={"tool": self.name},
            )
            return ToolSuccess(data=_TotalBalanceResponse(balance=balance))
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
