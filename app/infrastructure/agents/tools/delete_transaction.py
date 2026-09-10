from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.infrastructure.agents._core.user_context import get_user_context
from app.services.transaction_service import TransactionService

from .._core.contracts.agent_tool import AgentTool


class DeleteTransactionArgsSchema(BaseModel):
    query: UpdateTransactionQuery


class DeleteTransactionResponse(BaseModel):
    deleted: bool


class DeleteTransactionTool(
    AgentTool[DeleteTransactionArgsSchema, DeleteTransactionResponse]
):
    name: Literal["delete_transaction"] = "delete_transaction"
    args_schema: type[DeleteTransactionArgsSchema] = DeleteTransactionArgsSchema
    description: str = (
        "Deleta / cancela uma transação existente.\n"
        "Estratégias:\n"
        "\t- Se 'id' for informado: deleta diretamente por ID.\n"
        "\t- Caso contrário: localiza a transação mais recente que combine "
        "(match_text em source_text/description) "
        "E (date_local em America/Sao_Paulo), então deleta.\n"
        "Retorna verdadeiro se deletou algo, falso caso contrário"
    )

    service: Annotated[TransactionService, Field(exclude=True)]

    async def _execute(
        self, args: DeleteTransactionArgsSchema
    ) -> DeleteTransactionResponse:
        params = UpdateTransactionParams(query=args.query, is_canceled=True)
        await self.service.update_transaction(
            params, user_id=get_user_context().user_id
        )

        return DeleteTransactionResponse(deleted=True)
