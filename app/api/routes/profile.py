from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.models.user_context import UserContext
from app.domain.model.user_profile import UserProfile
from app.services.user_profile_service import UserProfileService

from ..dependencies import get_profile_service, get_user_context
from ..schemas.profile import SaveProfileRequest, SaveProfileResponse

router = APIRouter(prefix="/profile")


@router.post("", response_model=SaveProfileResponse)
async def save_profile(
    request: SaveProfileRequest,
    context: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[UserProfileService, Depends(get_profile_service)],
) -> SaveProfileResponse:
    profile = await service.save(
        UserProfile(user_id=context.user_id, **request.model_dump())
    )
    return SaveProfileResponse(
        user_id=profile.user_id,
        monthly_revenue=profile.monthly_revenue,
        objective=profile.objective,
        risk_tolerance=profile.risk_tolerance,
        preferences=profile.preferences,
    )
