from typing import Protocol
from uuid import UUID

from app.application.models.event_query import EventQuery
from app.domain.model.event import CalendarReceipt, Event, EventCreation, EventDraft


class EventRepository(Protocol):
    async def query(self, user_id: UUID, query: EventQuery) -> list[Event]: ...

    async def create(
        self,
        user_id: UUID,
        operation_id: UUID,
        draft: EventDraft,
        *,
        confirm: bool = False,
    ) -> tuple[EventCreation, bool]: ...

    async def operation(
        self, user_id: UUID, operation_id: UUID
    ) -> EventCreation | None: ...

    async def proposals(self, user_id: UUID) -> list[EventCreation]: ...

    async def save_receipt(
        self, user_id: UUID, operation_id: UUID, receipt: CalendarReceipt
    ) -> None: ...
