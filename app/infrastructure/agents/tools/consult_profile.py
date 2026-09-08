import json
from dataclasses import asdict
from typing import Annotated, Any, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.ports.logger import LoggerFactory
from app.infrastructure.agents._core.user_context import get_user_context
from app.services.user_profile_service import UserProfileService


class ConsultProfileArgs(BaseModel):
    query: str = Field(min_length=1, description="Pergunta financeira a contextualizar")


class ConsultProfileTool(BaseTool):
    name: Literal["consult_profile"] = "consult_profile"
    args_schema: type[BaseModel] = ConsultProfileArgs
    description: str = (
        "Consulta o perfil financeiro cadastrado e busca semanticamente suas "
        "preferências para fundamentar conselhos. Somente leitura; não altera dados."
    )
    service: Annotated[UserProfileService, Field(exclude=True)]
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _run(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError("Use the asynchronous tool")

    async def _arun(self, query: str) -> str:
        try:
            profile = await self.service.consult(
                query, user_id=get_user_context().user_id
            )
            if profile is None:
                return "Perfil não cadastrado. Oriente o usuário a usar a tela Perfil."
            fields = asdict(profile)
            del fields["user_id"]
            return json.dumps(fields, ensure_ascii=False, default=str)
        except Exception as error:
            self.logger_factory(__name__).exception(
                "Profile tool failed", exception=error
            )
            return (
                "Não foi possível consultar o perfil agora. "
                "Não suponha que ele não existe; peça para tentar novamente."
            )
