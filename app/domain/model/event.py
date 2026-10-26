from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class EventDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    source_text: str = Field(min_length=1, max_length=10000)
    start_time: AwareDatetime
    end_time: AwareDatetime
    location: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if not self.title.strip() or not self.source_text.strip():
            raise ValueError("Title and source text must not be blank")
        if self.end_time <= self.start_time:
            raise ValueError("End must be after start")
        return self


class Event(EventDraft):
    id: UUID
    recorded_at: datetime


class CalendarReceipt(BaseModel):
    state: Literal["not_connected", "pending", "succeeded", "failed", "unknown"]
    google_id: str | None = None
    link: str | None = None
    transport: Literal["mcp", "rest"] | None = None
    code: str | None = None


class EventCreation(BaseModel):
    operation_id: UUID
    event: Event | None = None
    proposal: EventDraft
    conflicts: list[Event] = Field(default_factory=list)
    requires_confirmation: bool = False
    google: CalendarReceipt = Field(
        default_factory=lambda: CalendarReceipt(state="pending")
    )

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.google.state == "succeeded" and not self.google.google_id:
            raise ValueError("Provider success requires a real event ID")
        if self.event is None and self.google.state == "succeeded":
            raise ValueError("Google success requires local persistence")
        return self
