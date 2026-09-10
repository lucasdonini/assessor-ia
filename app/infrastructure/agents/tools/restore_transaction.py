from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.infrastructure.agents._core.user_context import get_user_context
from app.services.transaction_service import TransactionService

from .._core.contracts.agent_tool import AgentTool


class RestoreTransactionArgsSchema(BaseModel):
    query: UpdateTransactionQuery


class RestoreTransactionResponse(BaseModel):
    restored: bool


class RestoreTransactionTool(
    AgentTool[RestoreTransactionArgsSchema, RestoreTransactionResponse]
):
    name: Literal["restore_transaction"] = "restore_transaction"
    args_schema: type[RestoreTransactionArgsSchema] = RestoreTransactionArgsSchema
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

    async def _execute(
        self, args: RestoreTransactionArgsSchema
    ) -> RestoreTransactionResponse:
        params = UpdateTransactionParams(query=args.query, is_canceled=False)
        await self.service.update_transaction(
            params, user_id=get_user_context().user_id
        )

        return RestoreTransactionResponse(restored=True)
