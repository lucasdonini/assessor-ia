from typing import Annotated, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.exceptions import ApplicationError
from app.application.models.transaction_query import (
    TransactionQueryParams,
)
from app.application.ports.logger import LoggerFactory
from app.infrastructure.agents._core.user_context import get_user_context
from app.infrastructure.agents.financial.schemas.tool_response import (
    ToolFailure,
    ToolResponse,
    ToolSuccess,
)
from app.infrastructure.agents.financial.schemas.transaction import TransactionOutput
from app.services.transaction_service import TransactionService


class _SearchTransactionsArgsSchema(BaseModel):
    params: TransactionQueryParams


class _SearchTransactionsResponse(BaseModel):
    transactions: list[TransactionOutput]


class SearchTransactionsTool(BaseTool):
    name: Literal["search_transactions"] = "search_transactions"
    args_schema: type[BaseModel] = _SearchTransactionsArgsSchema
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
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _run(
        self, params: TransactionQueryParams
    ) -> ToolResponse[_SearchTransactionsResponse]:
        raise NotImplementedError("This tool only supports asynchronous execution")

    async def _arun(
        self, params: TransactionQueryParams
    ) -> ToolResponse[_SearchTransactionsResponse]:
        logger = self.logger_factory(__name__)
        logger.debug(
            "Tool called",
            details={
                "tool": self.name,
                "filters": sorted(
                    key
                    for key, value in params.model_dump().items()
                    if value is not None and key != "source_text"
                ),
            },
        )
        try:
            result = await self.service.search_transactions(
                params, user_id=get_user_context().user_id
            )
            logger.debug(
                "Tool succeeded",
                details={"tool": self.name, "count": len(result)},
            )
            return ToolSuccess(
                data=_SearchTransactionsResponse(
                    transactions=[
                        TransactionOutput.from_domain(item) for item in result
                    ]
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
