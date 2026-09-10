from datetime import date
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


class _DailyBalanceArgsSchema(BaseModel):
    target_date: date = Field(
        ...,
        description=(
            "Data de referência para o cálculo do saldo. "
            "O saldo retornado será o acumulado de todas as entradas (INCOME) "
            "e saídas (EXPENSES), ignorando transferências (TRANSFER)"
            "registradas ATÉ esse dia (inclusive). "
            "Exemplos: 'qual meu saldo hoje' → {hoje}, "
            "'qual era meu saldo no fim de março' → 2026-03-31."
        ),
    )


class _DailyBalanceResponse(BaseModel):
    balance: float
    date: date


class DailyBalanceTool(BaseTool):
    name: Literal["daily_balance"] = "daily_balance"
    args_schema: type[BaseModel] = _DailyBalanceArgsSchema
    description: str = (
        "Retorna o saldo (INCOME - EXPENSES) do dia local informado "
        "em America/Sao_Paulo. Ignora TRANSFER (type=3)"
    )

    service: Annotated[TransactionService, Field(exclude=True)]
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _run(self, target_date: date) -> ToolResponse[_DailyBalanceResponse]:
        raise NotImplementedError("This tool only supports asynchronous execution")

    async def _arun(self, target_date: date) -> ToolResponse[_DailyBalanceResponse]:
        logger = self.logger_factory(__name__)
        logger.debug(
            "Tool called",
            details={"tool": self.name, "target_date": str(target_date)},
        )
        try:
            balance = await self.service.calculate_daily_balance(
                target_date, user_id=get_user_context().user_id
            )
            logger.debug(
                "Tool succeeded",
                details={"tool": self.name},
            )
            response = _DailyBalanceResponse(balance=balance, date=target_date)
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
