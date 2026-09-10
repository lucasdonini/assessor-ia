from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.infrastructure.agents._core.user_context import get_user_context
from app.infrastructure.agents.financial.schemas.transaction import (
    TransactionInput,
    TransactionOutput,
)
from app.services.transaction_service import TransactionService

from .._core.contracts.agent_tool import AgentTool


class AddTransactionArgsSchema(BaseModel):
    transaction: TransactionInput


class AddTransactionResponse(BaseModel):
    transaction: TransactionOutput


class AddTransactionTool(AgentTool[AddTransactionArgsSchema, AddTransactionResponse]):
    name: Literal["add_transaction"] = "add_transaction"
    args_schema: type[AddTransactionArgsSchema] = AddTransactionArgsSchema
    description: str = "Insere uma transação financeira no banco de dados PosthreSQL."

    service: Annotated[TransactionService, Field(exclude=True)]

    async def _execute(self, args: AddTransactionArgsSchema) -> AddTransactionResponse:
        transaction = args.transaction

        added = await self.service.add_transaction(
            transaction.to_domain(user_id=get_user_context().user_id),
            user_id=get_user_context().user_id,
        )

        return AddTransactionResponse(transaction=TransactionOutput.from_domain(added))
