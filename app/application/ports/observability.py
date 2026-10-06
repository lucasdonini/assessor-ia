from contextlib import AbstractContextManager
from typing import Protocol

from app.application.models.observability import ObservationSnapshot, Outcome


class TurnRecorder(Protocol):
    @property
    def callbacks(self) -> tuple[object, ...]: ...

    def turn(
        self, turn_id: str, user_id: str, session_id: str
    ) -> AbstractContextManager[None]: ...

    def node(self, name: str) -> AbstractContextManager[None]: ...

    def select_route(self, name: str) -> None: ...

    def classify(self, status: Outcome, reason: str | None = None) -> None: ...

    def fallback(self) -> None: ...


class ObservationReader(Protocol):
    def snapshot(self, user_id: str) -> ObservationSnapshot: ...
