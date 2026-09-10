from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.domain.model.user_profile import RiskTolerance
from app.infrastructure.agents._core.user_context import get_user_context
from app.services.user_profile_service import UserProfileService

from .._core.contracts.agent_tool import AgentTool


class ConsultProfileArgsSchema(BaseModel):
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


class ConsultProfileTool(AgentTool[ConsultProfileArgsSchema, ConsultProfileResponse]):
    name: Literal["consult_profile"] = "consult_profile"
    args_schema: type[ConsultProfileArgsSchema] = ConsultProfileArgsSchema
    description: str = (
        "Consulta o perfil financeiro cadastrado e busca semanticamente suas "
        "preferências para fundamentar conselhos. Somente leitura; não altera dados."
    )

    service: Annotated[UserProfileService, Field(exclude=True)]

    async def _execute(self, args: ConsultProfileArgsSchema) -> ConsultProfileResponse:
        query = args.query
        profile = await self.service.consult(query, user_id=get_user_context().user_id)

        return (
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
