import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.application.models.event_query import EventQuery
from app.domain.model.event import CalendarReceipt, Event, EventCreation, EventDraft
from app.services.event_service import EventService


def draft():
    return EventDraft(
        title="Reunião",
        source_text="marque reunião",
        start_time="2026-10-27T14:00:00-03:00",
        end_time="2026-10-27T15:00:00-03:00",
    )


def creation():
    event = draft()
    return EventCreation(
        operation_id=uuid4(),
        proposal=event,
        event=Event(**event.model_dump(), id=uuid4(), recorded_at=event.start_time),
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"end_time": None},
        {"start_time": "2026-10-27T14:00:00"},
        {"end_time": "2026-10-27T12:00:00-03:00"},
        {"title": " "},
    ],
)
def test_invalid_event_input(updates):
    with pytest.raises(ValidationError):
        EventDraft.model_validate(draft().model_dump() | updates)


@pytest.mark.parametrize(
    "updates",
    [
        {"limit": 0},
        {"limit": 201},
        {"date_local": "2026-10-27", "date_from_local": "2026-10-26"},
        {"date_from_local": "2026-10-28", "date_to_local": "2026-10-27"},
    ],
)
def test_invalid_event_query(updates):
    with pytest.raises(ValidationError):
        EventQuery.model_validate(updates)


@pytest.mark.asyncio
async def test_local_commit_precedes_remote_and_failure_retains_event():
    repository, calendar = AsyncMock(), AsyncMock()
    result = creation()
    order = []

    async def commit(*args, **kwargs):
        order.append("commit")
        return result, True

    async def export(*args):
        order.append("google")
        return CalendarReceipt(state="failed", code="denied")

    repository.create.side_effect = commit
    calendar.create.side_effect = export
    response = await EventService(repository, calendar).create(
        uuid4(), result.operation_id, result.proposal
    )
    assert order == ["commit", "google"]
    assert response.event == result.event and response.google.state == "failed"
    repository.save_receipt.assert_awaited_once()


@pytest.mark.asyncio
async def test_local_failure_never_calls_remote():
    repository, calendar = AsyncMock(), AsyncMock()
    repository.create.side_effect = RuntimeError("db")
    with pytest.raises(RuntimeError):
        await EventService(repository, calendar).create(uuid4(), uuid4(), draft())
    calendar.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_or_conflicting_operation_does_not_export():
    repository, calendar = AsyncMock(), AsyncMock()
    result = EventCreation(
        operation_id=uuid4(), proposal=draft(), requires_confirmation=True
    )
    repository.create.return_value = (result, False)
    assert (
        await EventService(repository, calendar).create(
            uuid4(), result.operation_id, result.proposal
        )
        == result
    )
    calendar.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_after_timeout_is_persisted():
    repository, calendar = AsyncMock(), AsyncMock()
    result = creation()
    repository.create.return_value = (result, True)
    calendar.create.side_effect = TimeoutError()
    response = await EventService(repository, calendar).create(
        uuid4(), result.operation_id, result.proposal
    )
    assert response.google.state == "unknown"


@pytest.mark.asyncio
async def test_cancellation_propagates_without_retry():
    repository, calendar = AsyncMock(), AsyncMock()
    result = creation()
    repository.create.return_value = (result, True)
    calendar.create.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await EventService(repository, calendar).create(
            uuid4(), result.operation_id, result.proposal
        )
    repository.save_receipt.assert_not_awaited()


def test_google_success_requires_evidence():
    with pytest.raises(ValidationError):
        EventCreation(
            operation_id=uuid4(),
            proposal=draft(),
            google=CalendarReceipt(state="succeeded"),
        )
