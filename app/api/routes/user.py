from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_user_service
from app.domain.model.user import User
from app.services.user_service import UserService

router = APIRouter(prefix="/users")


@router.post("", status_code=201)
async def create_user(
    service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    return await service.create()


@router.get("")
async def list_users(
    service: Annotated[UserService, Depends(get_user_service)],
) -> list[User]:
    return await service.list_users()
