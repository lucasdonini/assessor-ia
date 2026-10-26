from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import authenticated_session
from app.application.models.google_identity import WebSession
from app.domain.model.event import EventCreation
from app.services.event_service import EventService

router = APIRouter(prefix="/agenda")


@router.get("/proposals")
@inject
async def proposals(
    session: Annotated[WebSession, Depends(authenticated_session)],
    service: FromDishka[EventService],
) -> list[EventCreation]:
    return await service.proposals(session.user_id)


@router.post("/proposals/{operation_id}/confirm")
@inject
async def confirm(
    operation_id: UUID,
    session: Annotated[WebSession, Depends(authenticated_session)],
    service: FromDishka[EventService],
) -> EventCreation:
    result = await service.confirm(session.user_id, operation_id)
    if result is None:
        raise HTTPException(404, "Proposta não encontrada.")
    return result
