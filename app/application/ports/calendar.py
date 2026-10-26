from typing import Protocol
from uuid import UUID

from app.domain.model.event import CalendarReceipt, EventDraft


class CalendarGateway(Protocol):
    async def create(self, user_id: UUID, event: EventDraft) -> CalendarReceipt: ...
