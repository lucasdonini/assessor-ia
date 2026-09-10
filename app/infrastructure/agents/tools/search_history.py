from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.domain.model.chat_session import ChatSessionSummarized
from app.infrastructure.agents._core.user_context import get_user_context
from app.services.chat_history_service import ChatHistoryService

from .._core.contracts.agent_tool import AgentTool


class SearchHistoryArgsSchema(BaseModel):
    search: Annotated[
        str, Field(description="Assunto ou pergunta sobre conversas anteriores")
    ]


class SearchHistoryResponse(BaseModel):
    history: str


class SearchHistoryTool(AgentTool[SearchHistoryArgsSchema, SearchHistoryResponse]):
    args_schema: type[SearchHistoryArgsSchema] = SearchHistoryArgsSchema
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

    def _format_history(self, history: list[ChatSessionSummarized]) -> str:
        return "\n\n".join(f"[{h.started_at:%d/%m/%Y}] {h.summary}" for h in history)

    async def _execute(self, args: SearchHistoryArgsSchema) -> SearchHistoryResponse:
        history = await self.service.fetch_history(
            user_id=get_user_context().user_id,
            search=args.search,
            limit=3,
        )

        return SearchHistoryResponse(
            history=(
                self._format_history(history)
                if history
                else "Nenhuma conversa anterior relevante foi encontrada."
            )
        )
