from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.infrastructure.agents._core.user_context import get_user_context
from app.services.transaction_service import TransactionService

from .._core.contracts.agent_tool import AgentTool


class DailyBalanceArgsSchema(BaseModel):
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


class DailyBalanceResponse(BaseModel):
    balance: float
    date: date


class DailyBalanceTool(AgentTool[DailyBalanceArgsSchema, DailyBalanceResponse]):
    name: Literal["daily_balance"] = "daily_balance"
    args_schema: type[DailyBalanceArgsSchema] = DailyBalanceArgsSchema
    description: str = (
        "Retorna o saldo (INCOME - EXPENSES) do dia local informado "
        "em America/Sao_Paulo. Ignora TRANSFER (type=3)"
    )

    service: Annotated[TransactionService, Field(exclude=True)]

    async def _execute(self, args: DailyBalanceArgsSchema) -> DailyBalanceResponse:
        target_date = args.target_date
        balance = await self.service.calculate_daily_balance(
            target_date, user_id=get_user_context().user_id
        )

        return DailyBalanceResponse(balance=balance, date=target_date)
