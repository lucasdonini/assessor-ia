"""Real HTTP client against a running local Postman simulation; no Google writes."""

import asyncio
import os
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest

from app.domain.model.event import EventDraft
from app.infrastructure.config import GoogleConfig
from app.infrastructure.google_calendar import GoogleCalendarGateway

pytestmark = pytest.mark.integration


class SyntheticAuth:
    @asynccontextmanager
    async def calendar_access(self, user_id):
        yield "synthetic-token"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,state,transport,count",
    [
        ("success", "succeeded", "mcp", 1),
        ("disabled", "succeeded", "rest", 1),
        ("denied", "failed", "mcp", 0),
        ("tool-error", "failed", "mcp", 0),
        ("preview-required", "failed", "mcp", 0),
        ("server-error", "unknown", "mcp", 1),
    ],
)
async def test_real_gateway_over_simulated_http(mode, state, transport, count):
    base = os.environ.get("CALENDAR_SIMULATION_URL")
    if not base:
        pytest.skip("Start Postman simulation and set CALENDAR_SIMULATION_URL")
    async with httpx.AsyncClient() as client:
        await client.delete(base + "/records")
    gateway = GoogleCalendarGateway(
        SyntheticAuth(), GoogleConfig(mcp_url=base + "/mcp/" + mode, rest_url=base)
    )
    event = EventDraft(
        title="Synthetic meeting",
        source_text="test",
        start_time="2026-10-27T14:00:00-03:00",
        end_time="2026-10-27T15:00:00-03:00",
    )
    async with asyncio.timeout(8):
        receipt = await gateway.create(uuid4(), event)
    assert receipt.state == state
    assert receipt.transport == transport
    if mode == "preview-required":
        assert receipt.error_category == "preview_required"
    async with httpx.AsyncClient() as client:
        records = (await client.get(base + "/records")).json()
    assert len(records) == count
    if state == "succeeded":
        assert receipt.google_id == records[0]["id"]
