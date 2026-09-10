from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.infrastructure.agents._core.user_context import get_user_context
from app.services.transaction_service import TransactionService

from .._core.contracts.agent_tool import AgentTool


class TotalBalanceArgsSchema(BaseModel):
    pass


class TotalBalanceResponse(BaseModel):
    balance: float


class TotalBalanceTool(AgentTool[TotalBalanceArgsSchema, TotalBalanceResponse]):
    name: Literal["total_balance"] = "total_balance"
    args_schema: type[TotalBalanceArgsSchema] = TotalBalanceArgsSchema
    description: str = (
        "Recupera do banco de dados o saldo atual "
        "a partir de todas as transações registradas"
    )

    service: Annotated[TransactionService, Field(exclude=True)]

    async def _execute(self, args: TotalBalanceArgsSchema) -> TotalBalanceResponse:
        balance = await self.service.calculate_total_balance(
            user_id=get_user_context().user_id
        )

        return TotalBalanceResponse(balance=balance)
