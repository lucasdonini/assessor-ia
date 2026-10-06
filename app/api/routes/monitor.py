from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.models.user_context import UserContext
from app.services.monitoring_service import MonitoringService

from ..dependencies import get_monitoring_service, get_user_context
from ..schemas.monitor import MonitorResponse

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("")
async def monitor(
    context: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[MonitoringService, Depends(get_monitoring_service)],
) -> MonitorResponse:
    return MonitorResponse.model_validate(service.get_monitor(str(context.user_id)))
