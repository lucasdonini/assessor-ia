from typing import Annotated, Literal

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.exceptions import ApplicationError
from app.application.ports.faq_search import FaqSearch
from app.application.ports.logger import LoggerFactory

from .._core.schemas.tool_response import (
    ToolFailure,
    ToolResponse,
    ToolSuccess,
)


class GetFAQAnswerArgsSchema(BaseModel):
    question: str = Field(..., description="Pergunta do usuário a ser respondida")


class GetFAQAnswerResponse(BaseModel):
    response: list[str]


class FaqRag(BaseTool):
    name: Literal["faq_rag"] = "faq_rag"
    args_schema: type[BaseModel] = GetFAQAnswerArgsSchema
    description: str = (
        "Busca no FAQ oficial os trechos relevantes para responder a pergunta."
    )

    faq_search: Annotated[FaqSearch, Field(exclude=True)]
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _run(self, question: str) -> ToolResponse[GetFAQAnswerResponse]:
        logger = self.logger_factory(__name__)
        logger.debug("Tool called", details={"tool": self.name})

        try:
            result = self.faq_search.search(question, limit=6)
            if result == []:
                result.append(
                    "Não foi encontrada nenhuma informação relevante "
                    "sobre isso no pdf de FAQ"
                )
            return ToolSuccess(data=GetFAQAnswerResponse(response=result))
        except ApplicationError as error:
            return ToolFailure.application_error(error)
        except Exception:
            return ToolFailure.unexpected_error()
