import asyncio
from uuid import UUID

from app.application.models.event_query import EventQuery
from app.application.ports.calendar import CalendarGateway
from app.application.repositories.event_repository import EventRepository
from app.domain.model.event import CalendarReceipt, Event, EventCreation, EventDraft


class EventService:
    def __init__(self, repository: EventRepository, calendar: CalendarGateway) -> None:
        self._repository = repository
        self._calendar = calendar

    async def query(self, user_id: UUID, query: EventQuery) -> list[Event]:
        return await self._repository.query(user_id, query)

    async def proposals(self, user_id: UUID) -> list[EventCreation]:
        return await self._repository.proposals(user_id)

    async def create(
        self,
        user_id: UUID,
        operation_id: UUID,
        draft: EventDraft,
        *,
        confirm: bool = False,
    ) -> EventCreation:
        result, created = await self._repository.create(
            user_id, operation_id, draft, confirm=confirm
        )
        if not created:
            return result
        try:
            async with asyncio.timeout(30):
                receipt = await self._calendar.create(user_id, draft)
        except TimeoutError:
            receipt = CalendarReceipt(state="unknown", code="provider_timeout")
        except asyncio.CancelledError:
            # Durable pending is intentionally not retried after cancellation.
            raise
        except Exception:
            receipt = CalendarReceipt(state="unknown", code="provider_unavailable")
        await self._repository.save_receipt(user_id, operation_id, receipt)
        result.google = receipt
        return result

    async def confirm(self, user_id: UUID, operation_id: UUID) -> EventCreation | None:
        previous = await self._repository.operation(user_id, operation_id)
        if previous is None:
            return None
        return await self.create(user_id, operation_id, previous.proposal, confirm=True)
