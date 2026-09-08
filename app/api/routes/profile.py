from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.models.user_context import UserContext

from ..dependencies import get_user_context
from ..schemas.profile import SaveProfileRequest, SaveProfileResponse

router = APIRouter(prefix="/profile")


@router.post("", response_model=SaveProfileResponse)
async def save_profile(
    request: SaveProfileRequest,
    context: Annotated[UserContext, Depends(get_user_context)],
) -> SaveProfileResponse:
    return SaveProfileResponse(user_id=context.user_id, **request.model_dump())
