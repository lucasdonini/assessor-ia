from typing import Protocol

from app.application.models.observability import TelemetrySnapshot


class TelemetryReader(Protocol):
    def snapshot(self) -> TelemetrySnapshot: ...
