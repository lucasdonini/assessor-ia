from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.application.models.transaction_update import (
    UpdateTransactionParams,
)
from app.infrastructure.agents._core.user_context import get_user_context
from app.infrastructure.agents.financial.schemas.transaction import TransactionOutput
from app.services.transaction_service import TransactionService

from .._core.contracts.agent_tool import AgentTool


class UpdateTransactionArgsSchema(BaseModel):
    params: UpdateTransactionParams


class UpdateTransactionResponse(BaseModel):
    updated: TransactionOutput | None = None


class UpdateTransactionTool(
    AgentTool[UpdateTransactionArgsSchema, UpdateTransactionResponse]
):
    name: Literal["update_transaction"] = "update_transaction"
    args_schema: type[UpdateTransactionArgsSchema] = UpdateTransactionArgsSchema
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

    async def _execute(
        self, args: UpdateTransactionArgsSchema
    ) -> UpdateTransactionResponse:
        updated = await self.service.update_transaction(
            args.params, user_id=get_user_context().user_id
        )

        return UpdateTransactionResponse(updated=TransactionOutput.from_domain(updated))
