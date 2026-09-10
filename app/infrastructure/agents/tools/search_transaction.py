from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.infrastructure.agents._core.user_context import get_user_context
from app.infrastructure.agents.financial.schemas.transaction import TransactionOutput
from app.services.transaction_service import TransactionService

from .._core.contracts.agent_tool import AgentTool


class SearchTransactionsArgsSchema(BaseModel):
    params: TransactionQueryParams


class SearchTransactionsResponse(BaseModel):
    transactions: list[TransactionOutput]


class SearchTransactionsTool(
    AgentTool[SearchTransactionsArgsSchema, SearchTransactionsResponse]
):
    name: Literal["search_transactions"] = "search_transactions"
    args_schema: type[SearchTransactionsArgsSchema] = SearchTransactionsArgsSchema
    description: str = (
        "Busca no banco de dados uma transação de acordo com os parâmetros passados. "
        "Caso nenhum parâmetro seja passado, retorna as útlimas 10 transações. "
        "Se a data de início for passada mas a de final não, retorna todas desde o "
        "início até hoje. "
        "Se a data de início não for passada mas a de final for, retora todas até a "
        "data de final. "
        "Buscar usando parâmetros como source_text e description pode ser ineficiente, "
        "uma vez que são textos humanos, o que os torna menos padronizados. "
        "Buscas por source_text ou description fazem busca parcial para permitir "
        "que transações com description "
        "'fiz uma doação para ...' sejam retornadas buscando apenas por 'doação'."
    )

    service: Annotated[TransactionService, Field(exclude=True)]

    async def _execute(
        self, args: SearchTransactionsArgsSchema
    ) -> SearchTransactionsResponse:
        result = await self.service.search_transactions(
            args.params, user_id=get_user_context().user_id
        )

        return SearchTransactionsResponse(
            transactions=[TransactionOutput.from_domain(item) for item in result]
        )
