from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.model.user_profile import RiskTolerance


class SaveProfileRequest(BaseModel):
    monthly_revenue: Annotated[
        Decimal,
        Field(gt=0, description="The user's monthly revenue"),
    ]

    objective: Annotated[
        str,
        Field(
            min_length=1,
            max_length=120,
            description="A short phrase stating the user's objective",
        ),
    ]

    risk_tolerance: Annotated[
        RiskTolerance,
        Field(
            description=(
                "Identifies how much risk the user accepts in financial operations"
            )
        ),
    ]

    preferences: Annotated[
        str,
        Field(
            min_length=1,
            description="Free text with phrases stating the user's preferences",
        ),
    ]


class SaveProfileResponse(SaveProfileRequest):
    user_id: UUID
