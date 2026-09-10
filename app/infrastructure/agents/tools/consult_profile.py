from decimal import Decimal
from typing import Annotated, Any, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.exceptions import ApplicationError
from app.application.ports.logger import LoggerFactory
from app.domain.model.user_profile import RiskTolerance
from app.infrastructure.agents._core.schemas.tool_response import (
    ToolFailure,
    ToolResponse,
    ToolSuccess,
)
from app.infrastructure.agents._core.user_context import get_user_context
from app.services.user_profile_service import UserProfileService


class ConsultProfileArgs(BaseModel):
    query: str = Field(min_length=1, description="Pergunta financeira a contextualizar")


class ConsultProfileResponse(BaseModel):
    status: str


class ConsultProfileNotFoundResponse(ConsultProfileResponse):
    status: Literal["not_found"] = "not_found"
    detail: str


class ConsultProfileFoundResponse(ConsultProfileResponse):
    status: Literal["found"] = "found"
    monthly_revenue: Decimal
    objective: str
    risk_tolerance: RiskTolerance
    preferences: str


class ConsultProfileTool(BaseTool):
    name: Literal["consult_profile"] = "consult_profile"
    args_schema: type[BaseModel] = ConsultProfileArgs
    description: str = (
        "Consulta o perfil financeiro cadastrado e busca semanticamente suas "
        "preferências para fundamentar conselhos. Somente leitura; não altera dados."
    )

    service: Annotated[UserProfileService, Field(exclude=True)]
    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]

    def _run(self, *args: Any, **kwargs: Any) -> ToolResponse[ConsultProfileResponse]:
        raise NotImplementedError("Use the asynchronous tool")

    async def _arun(self, query: str) -> ToolResponse[ConsultProfileResponse]:
        try:
            profile = await self.service.consult(
                query, user_id=get_user_context().user_id
            )

            response = (
                ConsultProfileNotFoundResponse(
                    detail=(
                        "Perfil não cadastrado. Oriente o usuário a usar a tela Perfil."
                    )
                )
                if profile is None
                else ConsultProfileFoundResponse(
                    monthly_revenue=profile.monthly_revenue,
                    objective=profile.objective,
                    risk_tolerance=profile.risk_tolerance,
                    preferences=profile.preferences,
                )
            )

            return ToolSuccess(data=response)

        except ApplicationError as error:
            return ToolFailure.application_error(error)
        except Exception as error:
            self.logger_factory(__name__).exception(
                "Profile tool failed",
                exception=error,
            )
            return ToolFailure.unexpected_error()
