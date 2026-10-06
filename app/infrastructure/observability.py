"""Process-local, content-free telemetry. Never retain callback payloads."""

import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
from typing import Any, Iterator
from uuid import UUID, uuid4

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.application.models.observability import (
    ModelObservation,
    NodeObservation,
    ObservationSnapshot,
    Outcome,
    TurnObservation,
)

# Full text rates per million; verified 2026-10-06. No cache discounts.
# https://ai.google.dev/gemini-api/docs/pricing.md
# https://console.groq.com/docs/models
# Qwen 3.6 is absent from the current rate table: deliberately unpriced.
PRICES: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
    ("google", "gemini-2.5-flash"): (Decimal("0.30"), Decimal("2.50")),
    ("groq", "openai/gpt-oss-120b"): (Decimal("0.15"), Decimal("0.60")),
}
DETAIL_LIMIT = 1000


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class _Attempt:
    node: str
    provider: str
    model: str
    started_at: datetime
    start: float
    fallback: bool


@dataclass(slots=True)
class _Turn:
    turn_id: str
    user_id: str
    session_id: str
    started_at: datetime = field(default_factory=_now)
    start: float = field(default_factory=time.perf_counter)
    route: str = "none"
    status: Outcome = "ok"
    reason: str | None = None
    nodes: list[NodeObservation] = field(default_factory=list)
    attempts: list[ModelObservation] = field(default_factory=list)
    runs: dict[str, _Attempt] = field(default_factory=dict)
    fallbacks: int = 0
    complete: bool = True
    truncated: bool = False


class InMemoryObservability(BaseCallbackHandler):
    raise_error = False
    run_inline = True

    def __init__(self, capacity: int = 50) -> None:
        if capacity < 1:
            raise ValueError("Capacity must be positive")
        self._capacity = capacity
        self._lock = Lock()
        self._closed: deque[TurnObservation] = deque(maxlen=capacity)
        self._active: dict[str, _Turn] = {}
        self._turn_id: ContextVar[str | None] = ContextVar("obs_turn", default=None)
        self._node: ContextVar[str] = ContextVar("obs_node", default="unknown")
        self._fallback: ContextVar[bool] = ContextVar("obs_fallback", default=False)
        self._process_id = str(uuid4())
        self._started_at = _now()
        self._start = time.perf_counter()

    @property
    def callbacks(self) -> tuple[object, ...]:
        return (self,)

    def _current(self) -> _Turn | None:
        turn_id = self._turn_id.get()
        return self._active.get(turn_id) if turn_id is not None else None

    @contextmanager
    def turn(self, turn_id: str, user_id: str, session_id: str) -> Iterator[None]:
        token = self._turn_id.set(turn_id)
        try:
            with self._lock:
                self._active[turn_id] = _Turn(turn_id, user_id, session_id)
            try:
                yield
            except BaseException as exc:
                self.classify(
                    "error" if isinstance(exc, Exception) else "cancelled",
                    "timeout" if isinstance(exc, TimeoutError) else "execution_failed",
                )
                raise
            finally:
                self._close(turn_id)
        finally:
            self._turn_id.reset(token)

    def _close(self, turn_id: str) -> None:
        with self._lock:
            turn = self._active.pop(turn_id, None)
            if turn is None:
                return
            if turn.runs:
                turn.complete = False
                for run_id, attempt in turn.runs.items():
                    self._append_attempt(turn, run_id, attempt, "cancelled", None, None)
            self._closed.append(
                TurnObservation(
                    turn.turn_id,
                    turn.user_id,
                    turn.session_id,
                    turn.started_at,
                    _now(),
                    (time.perf_counter() - turn.start) * 1000,
                    turn.route,
                    turn.status,
                    turn.reason,
                    tuple(turn.nodes),
                    tuple(turn.attempts),
                    turn.fallbacks,
                    turn.complete,
                    turn.truncated,
                )
            )

    @contextmanager
    def node(self, name: str) -> Iterator[None]:
        token = self._node.set(name)
        fallback_token = self._fallback.set(False)
        start = time.perf_counter()
        status: Outcome = "ok"
        try:
            yield
        except BaseException as exc:
            status = "error" if isinstance(exc, Exception) else "cancelled"
            raise
        finally:
            with self._lock:
                if turn := self._current():
                    if status == "ok" and turn.status in {"error", "blocked"}:
                        status = turn.status
                    if len(turn.nodes) < DETAIL_LIMIT:
                        turn.nodes.append(
                            NodeObservation(
                                name, (time.perf_counter() - start) * 1000, status
                            )
                        )
                    else:
                        turn.truncated = True
                        turn.complete = False
            self._fallback.reset(fallback_token)
            self._node.reset(token)

    def select_route(self, name: str) -> None:
        with self._lock:
            if turn := self._current():
                turn.route = name

    def classify(self, status: Outcome, reason: str | None = None) -> None:
        with self._lock:
            if turn := self._current():
                turn.status, turn.reason = status, reason

    def fallback(self) -> None:
        self._fallback.set(True)
        with self._lock:
            if turn := self._current():
                turn.fallbacks += 1

    def snapshot(self, user_id: str) -> ObservationSnapshot:
        with self._lock:
            return ObservationSnapshot(
                self._process_id,
                self._started_at,
                _now(),
                time.perf_counter() - self._start,
                self._capacity,
                tuple(turn for turn in self._closed if turn.user_id == user_id),
                sum(turn.user_id == user_id for turn in self._active.values()),
            )

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            turn = self._current()
            if turn is None or str(run_id) in turn.runs:
                return
            if len(turn.attempts) + len(turn.runs) >= DETAIL_LIMIT:
                turn.truncated = True
                turn.complete = False
                return
            meta = metadata or {}
            params = kwargs.get("invocation_params") or {}
            model = str(
                meta.get("ls_model_name")
                or params.get("model_name")
                or params.get("model")
                or "unknown"
            ).removeprefix("models/")
            provider = str(meta.get("ls_provider") or "unknown")
            if provider in {"google_genai", "google_vertexai"}:
                provider = "google"
            turn.runs[str(run_id)] = _Attempt(
                self._node.get(),
                provider,
                model,
                _now(),
                time.perf_counter(),
                self._fallback.get(),
            )
            self._fallback.set(False)

    def _append_attempt(
        self,
        turn: _Turn,
        run_id: str,
        attempt: _Attempt,
        status: Outcome,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> None:
        rates = PRICES.get((attempt.provider, attempt.model))
        cost = None
        if rates and input_tokens is not None and output_tokens is not None:
            cost = (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000
        turn.attempts.append(
            ModelObservation(
                run_id,
                attempt.node,
                attempt.provider,
                attempt.model,
                attempt.started_at,
                _now(),
                (time.perf_counter() - attempt.start) * 1000,
                status,
                input_tokens,
                output_tokens,
                cost,
                attempt.fallback,
            )
        )

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            turn = self._current()
            if turn is None or (attempt := turn.runs.pop(str(run_id), None)) is None:
                return
            try:
                generation = response.generations[0][0]
                message = getattr(generation, "message", None)
                meta = getattr(message, "response_metadata", {}) or {}
                usage = getattr(message, "usage_metadata", None)
                if usage is None:
                    usage = meta.get("token_usage") or meta.get("usage") or {}
                model = meta.get("model_name") or meta.get("model")
                if model:
                    attempt.model = str(model).removeprefix("models/")
                incoming = usage.get("input_tokens", usage.get("prompt_tokens"))
                outgoing = usage.get("output_tokens", usage.get("completion_tokens"))
                incoming = incoming if type(incoming) is int and incoming >= 0 else None
                outgoing = outgoing if type(outgoing) is int and outgoing >= 0 else None
                self._append_attempt(
                    turn, str(run_id), attempt, "ok", incoming, outgoing
                )
            except Exception:
                turn.complete = False
                self._append_attempt(turn, str(run_id), attempt, "ok", None, None)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        with self._lock:
            turn = self._current()
            if turn is not None and (attempt := turn.runs.pop(str(run_id), None)):
                self._append_attempt(turn, str(run_id), attempt, "error", None, None)
