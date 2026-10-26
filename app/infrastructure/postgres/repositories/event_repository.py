from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.exceptions import ApplicationError
from app.application.models.event_query import EventQuery
from app.domain.model.event import CalendarReceipt, Event, EventCreation, EventDraft
from app.infrastructure.postgres.entities.event import EventOperationORM, EventORM


class InvalidEventProposal(ApplicationError):
    code = "invalid_event_proposal"
    public_message = "A proposta expirou ou mudou. Solicite o agendamento novamente."


def event_model(row: EventORM) -> Event:
    return Event(
        id=row.id,
        title=row.title,
        source_text=row.source_text,
        start_time=row.start_time,
        end_time=row.end_time,
        location=row.location,
        notes=row.notes,
        recorded_at=row.recorded_at,
    )


class SQLAlchemyEventRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def _lock(self, session: AsyncSession, user_id: UUID) -> None:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "agenda:" + str(user_id)},
        )

    async def query(self, user_id: UUID, query: EventQuery) -> list[Event]:
        statement = select(EventORM).where(EventORM.user_id == user_id)
        timezone = ZoneInfo("America/Sao_Paulo")
        start = query.date_local or query.date_from_local
        end = query.date_local or query.date_to_local
        if start:
            statement = statement.where(
                EventORM.start_time >= datetime.combine(start, time.min, timezone)
            )
        if end:
            statement = statement.where(
                EventORM.start_time
                < datetime.combine(end + timedelta(days=1), time.min, timezone)
            )
        if query.text:
            pattern = (
                "%"
                + query.text.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
                + "%"
            )
            statement = statement.where(
                or_(
                    *(
                        column.ilike(pattern, escape="\\")
                        for column in (
                            EventORM.title,
                            EventORM.location,
                            EventORM.notes,
                            EventORM.source_text,
                        )
                    )
                )
            )
        async with self._factory() as session:
            rows = await session.scalars(
                statement.order_by(EventORM.start_time, EventORM.id).limit(query.limit)
            )
            return [event_model(row) for row in rows]

    async def create(
        self,
        user_id: UUID,
        operation_id: UUID,
        draft: EventDraft,
        *,
        confirm: bool = False,
    ) -> tuple[EventCreation, bool]:
        async with self._factory.begin() as session:
            await self._lock(session, user_id)
            operation = await session.get(EventOperationORM, operation_id)
            previous: EventCreation | None = None
            if operation:
                if operation.user_id != user_id:
                    raise InvalidEventProposal()
                previous = EventCreation.model_validate(operation.result)
                if previous.proposal != draft:
                    raise InvalidEventProposal()
                if previous.event is not None or not confirm:
                    return previous, False
                if operation.expires_at <= datetime.now(UTC):
                    raise InvalidEventProposal()
            elif confirm:
                raise InvalidEventProposal()

            rows = await session.scalars(
                select(EventORM)
                .where(
                    EventORM.user_id == user_id,
                    EventORM.start_time < draft.end_time,
                    EventORM.end_time > draft.start_time,
                )
                .order_by(EventORM.start_time, EventORM.id)
            )
            conflicts = [event_model(row) for row in rows]
            same_conflicts = previous is not None and previous.conflicts == conflicts
            needs_confirmation = bool(conflicts) and not (confirm and same_conflicts)
            result = EventCreation(
                operation_id=operation_id,
                proposal=draft,
                conflicts=conflicts,
                requires_confirmation=needs_confirmation,
            )
            if not needs_confirmation:
                event = EventORM(user_id=user_id, **draft.model_dump())
                session.add(event)
                await session.flush()
                await session.refresh(event)
                result.event = event_model(event)
            expiry = datetime.now(UTC) + timedelta(minutes=10)
            if operation:
                operation.result = result.model_dump(mode="json")
                operation.expires_at = expiry
            else:
                session.add(
                    EventOperationORM(
                        id=operation_id,
                        user_id=user_id,
                        result=result.model_dump(mode="json"),
                        expires_at=expiry,
                    )
                )
            return result, not needs_confirmation

    async def operation(
        self, user_id: UUID, operation_id: UUID
    ) -> EventCreation | None:
        async with self._factory() as session:
            row = await session.scalar(
                select(EventOperationORM).where(
                    EventOperationORM.id == operation_id,
                    EventOperationORM.user_id == user_id,
                )
            )
            return EventCreation.model_validate(row.result) if row else None

    async def proposals(self, user_id: UUID) -> list[EventCreation]:
        async with self._factory() as session:
            rows = await session.scalars(
                select(EventOperationORM)
                .where(
                    EventOperationORM.user_id == user_id,
                    EventOperationORM.expires_at > datetime.now(UTC),
                    EventOperationORM.result["requires_confirmation"]
                    .as_boolean()
                    .is_(True),
                )
                .order_by(EventOperationORM.expires_at, EventOperationORM.id)
            )
            return [EventCreation.model_validate(row.result) for row in rows]

    async def save_receipt(
        self, user_id: UUID, operation_id: UUID, receipt: CalendarReceipt
    ) -> None:
        async with self._factory.begin() as session:
            await self._lock(session, user_id)
            row = await session.get(EventOperationORM, operation_id)
            if row is None or row.user_id != user_id:
                raise InvalidEventProposal()
            result = EventCreation.model_validate(row.result)
            result.google = receipt
            row.result = result.model_dump(mode="json")
