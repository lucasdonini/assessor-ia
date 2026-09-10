from typing import Annotated, Any, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.exceptions import ApplicationError
from app.application.ports.logger import LoggerFactory
from app.domain.model.chat_session import ChatSessionSummarized
from app.infrastructure.agents._core.user_context import get_user_context
from app.services.chat_history_service import ChatHistoryService

from .._core.schemas.tool_response import ToolFailure, ToolResponse, ToolSuccess


class SearchHistoryArgsSchema(BaseModel):
    search: Annotated[
        str, Field(description="Assunto ou pergunta sobre conversas anteriores")
    ]


class SearchHistoryResponse(BaseModel):
    history: str


class SearchHistoryTool(BaseTool):
    args_schema: type[BaseModel] = SearchHistoryArgsSchema
    name: Literal["search_history"] = "search_history"
    description: str = (
        "Consulta conversas ANTERIORES do usuário (sessões já encerradas).\n\n"
        "Use SOMENTE quando a resposta depende de algo dito numa conversa passada"
        "— preferências, decisões ou planos que o usuário mencionou antes."
        "NÃO use para dados que estão no banco (gastos, saldos, eventos): isso é "
        "responsabilidade dos agentes especialistas que têm acesso a tools mais "
        "específicas para isso."
    )

    service: Annotated[ChatHistoryService, Field(exclude=True)]
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _format_history(self, history: list[ChatSessionSummarized]) -> str:
        return "\n\n".join(f"[{h.started_at:%d/%m/%Y}] {h.summary}" for h in history)

    def _run(self, *args: Any, **kwargs: Any) -> ToolResponse[SearchHistoryResponse]:
        raise NotImplementedError("This tool is stricktly assyncronal. Use _arun.")

    async def _arun(self, search: str) -> ToolResponse[SearchHistoryResponse]:
        logger = self.logger_factory(__name__)
        logger.debug(
            "Tool called",
            details={"tool": self.name, "search_length": len(search)},
        )
        try:
            history = await self.service.fetch_history(
                search=search, limit=3, user_id=get_user_context().user_id
            )
            return ToolSuccess(
                data=SearchHistoryResponse(
                    history=(
                        self._format_history(history)
                        if history
                        else "Nenhuma conversa anterior relevante foi encontrada."
                    )
                )
            )

        except ApplicationError as error:
            return ToolFailure.application_error(error)

        except Exception as e:
            logger.exception(
                "Tool failed",
                exception=e,
                details={"tool": self.name},
            )
            return ToolFailure.unexpected_error()
