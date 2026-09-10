import asyncio
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.application.ports.faq_search import FaqSearch

from .._core.contracts.agent_tool import AgentTool


class GetFAQAnswerArgsSchema(BaseModel):
    question: str = Field(..., description="Pergunta do usuário a ser respondida")


class GetFAQAnswerResponse(BaseModel):
    response: list[str]


class FaqRag(AgentTool[GetFAQAnswerArgsSchema, GetFAQAnswerResponse]):
    name: Literal["faq_rag"] = "faq_rag"
    args_schema: type[GetFAQAnswerArgsSchema] = GetFAQAnswerArgsSchema
    description: str = (
        "Busca no FAQ oficial os trechos relevantes para responder a pergunta."
    )

    faq_search: Annotated[FaqSearch, Field(exclude=True)]

    async def _execute(self, args: GetFAQAnswerArgsSchema) -> GetFAQAnswerResponse:
        result = await asyncio.to_thread(self.faq_search.search, args.question, limit=6)

        if result == []:
            result.append(
                "Não foi encontrada nenhuma informação relevante "
                "sobre isso no pdf de FAQ"
            )
        return GetFAQAnswerResponse(response=result)
