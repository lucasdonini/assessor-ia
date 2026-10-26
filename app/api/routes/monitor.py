from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.auth import authenticated_session
from app.api.dependencies import get_monitor_access, get_monitor_service
from app.api.schemas.monitor import MonitorSnapshot
from app.application.models.google_identity import WebSession
from app.services.monitor_service import MonitorAccess, MonitorService

router = APIRouter(tags=["Monitoring"])


@router.get(
    "/monitor",
    responses={
        401: {"description": "Sign in required"},
        403: {"description": "Operator access required"},
    },
)
def monitor(
    response: Response,
    session: Annotated[WebSession, Depends(authenticated_session)],
    access: Annotated[MonitorAccess, Depends(get_monitor_access)],
    service: Annotated[MonitorService, Depends(get_monitor_service)],
) -> MonitorSnapshot:
    if not access.allows(session.email):
        raise HTTPException(403, "Acesso restrito à operação.")
    response.headers["Cache-Control"] = "no-store"
    return service.snapshot()
