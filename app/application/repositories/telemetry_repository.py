from typing import Protocol

from app.application.models.observability import TurnObservation


class TelemetryRepository(Protocol):
    async def initialize(self) -> None: ...

    async def save(self, turn: TurnObservation) -> None: ...

    async def latest(self, limit: int) -> tuple[TurnObservation, ...]: ...
