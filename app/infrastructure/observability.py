import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
from threading import RLock
from typing import Any, ParamSpec
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.application.models.evidence import Judgment
from app.application.models.observability import (
    JudgmentObservation,
    ModelObservation,
    NodeObservation,
    PersistenceSummary,
    TelemetrySnapshot,
    TurnObservation,
    TurnStatus,
)
from app.application.ports.logger import LoggerFactory
from app.application.repositories.telemetry_repository import TelemetryRepository


@dataclass
class ActiveTurn:
    turn_id: str
    user_id: str
    session_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    start: float = field(default_factory=time.perf_counter)
    route: str = "unknown"
    status: TurnStatus = "ok"
    failure_category: str | None = None
    nodes: list[NodeObservation] = field(default_factory=list)
    calls: list[ModelObservation] = field(default_factory=list)
    fallbacks: int = 0
    completed: TurnObservation | None = None
    judgments: list[JudgmentObservation] = field(default_factory=list)
    financial_outcomes: tuple[str, ...] = ()


_current: ContextVar[tuple["TurnTelemetry", str] | None] = ContextVar(
    "telemetry_turn", default=None
)
_node: ContextVar[str] = ContextVar("telemetry_node", default="unknown")
_P = ParamSpec("_P")
_PERSISTENCE_TIMEOUT_SECONDS = 2.0


def best_effort(operation: Callable[_P, None]) -> Callable[_P, None]:
    @wraps(operation)
    def record(*args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            operation(*args, **kwargs)
        except Exception:
            # Never let diagnostics replace a business result or original failure.
            current = _current.get()
            if current:
                try:
                    current[0]._logger.warning("Telemetry recording unavailable")
                except Exception:
                    pass
            return

    return record


def observe_route(route: str) -> None:
    current = _current.get()
    if current:
        current[0].update(current[1], route=route)


def observe_block(reason: str) -> None:
    current = _current.get()
    if current:
        category = {
            "classificador_indisponivel": "classifier_unavailable",
            "classificacao_indeterminada": "classification_indeterminate",
        }.get(reason)
        current[0].update(
            current[1],
            route="blocked",
            status="error" if category else "blocked",
            category=category,
        )


def observe_fallback() -> None:
    current = _current.get()
    if current:
        current[0].fallback(current[1])


@best_effort
def observe_judgment(
    stage: str,
    result: "Judgment",
    elapsed_ms: float,
    attempted: bool,
    success: bool,
    usage: dict[str, object],
) -> None:
    current = _current.get()
    if not current:
        return
    store, turn_id = current
    with store._lock:
        turn = store._active.get(turn_id)
        if turn is None:
            return
        turn.judgments.append(
            JudgmentObservation(
                stage=stage,
                reason=result.reason,
                choice=result.choice,
                noul=result.noul,
                model=result.model,
                elapsed_ms=elapsed_ms,
            )
        )
        if attempted:
            turn.calls.append(
                ModelObservation(
                    provider="typesafe",
                    model=result.model or "jev-1.14.0",
                    node="evidence_judge"
                    if stage == "reply"
                    else "financial_validation",
                    elapsed_ms=elapsed_ms,
                    success=success,
                    input_tokens=_count(usage.get("input_tokens")),
                    output_tokens=_count(usage.get("output_tokens")),
                )
            )
        if not result.approved:
            turn.status = "blocked" if result.reason == "unsupported" else "error"
            turn.failure_category = "evidence_" + result.reason


@best_effort
def observe_financial_outcomes(outcomes: list[str]) -> None:
    current = _current.get()
    if not current or not outcomes:
        return
    store, turn_id = current
    with store._lock:
        turn = store._active.get(turn_id)
        if turn is None:
            return
        turn.financial_outcomes = tuple(outcomes)
        if "confirmed" in outcomes:
            turn.status = "ok"
            turn.failure_category = None
        elif "financial_outcome_unknown" in outcomes:
            turn.status = "error"
            turn.failure_category = "financial_outcome_unknown"
        elif turn.status == "ok":
            turn.status = "blocked"
            turn.failure_category = "financial_validation"


def has_active_turn() -> bool:
    return _current.get() is not None


@contextmanager
def observe_node(name: str) -> Generator[None]:
    token = _node.set(name)
    start = time.perf_counter()
    try:
        yield
    finally:
        current = _current.get()
        if current:
            current[0].node(current[1], name, (time.perf_counter() - start) * 1000)
        _node.reset(token)


class TurnTelemetry:
    """APP-scoped store. No prompt, reply, exception or tool payload is retained."""

    def __init__(
        self,
        logger_factory: LoggerFactory,
        repository: TelemetryRepository | None = None,
    ) -> None:
        self._logger = logger_factory(__name__)
        self._lock = RLock()
        self._started_at = datetime.now(UTC)
        self._start = time.perf_counter()
        self._turns: deque[TurnObservation] = deque(maxlen=50)
        self._active: dict[str, ActiveTurn] = {}
        self._runs: dict[UUID, tuple[str, str, str, str, float]] = {}
        self.callback = ModelCollector(self)
        self._repository = repository
        self._history_loaded = False
        self._failed_writes = 0
        self._pending: set[asyncio.Task[None]] = set()

    async def restore(self) -> None:
        if self._repository is None:
            return
        try:
            async with asyncio.timeout(_PERSISTENCE_TIMEOUT_SECONDS):
                await self._repository.initialize()
                turns = await self._repository.latest(50)
            with self._lock:
                self._turns.extend(turns)
                self._history_loaded = True
        except Exception:
            self._logger.warning("Telemetry history unavailable")

    async def _persist(self, turn: TurnObservation) -> None:
        if self._repository is None:
            return
        try:
            async with asyncio.timeout(_PERSISTENCE_TIMEOUT_SECONDS):
                try:
                    await self._repository.save(turn)
                except Exception:
                    # One bounded idempotent retry; never repeat a business operation.
                    await self._repository.save(turn)
        except Exception:
            self._failed_writes += 1
            self._logger.warning("Telemetry persistence unavailable")

    @asynccontextmanager
    async def persisted_turn(
        self, turn_id: str, user_id: str, session_id: str
    ) -> AsyncIterator[None]:
        active: ActiveTurn | None = None
        try:
            with self.turn(turn_id, user_id, session_id):
                active = self._active.get(turn_id)
                yield
        finally:
            if active is not None and active.completed is not None and self._repository:
                task = asyncio.create_task(self._persist(active.completed))
                self._pending.add(task)
                task.add_done_callback(self._pending.discard)
                # Keep the write alive if a caller cancels the graph task again.
                await asyncio.shield(task)

    async def drain(self) -> None:
        if self._pending:
            await asyncio.gather(*tuple(self._pending), return_exceptions=True)

    @contextmanager
    def turn(self, turn_id: str, user_id: str, session_id: str) -> Generator[None]:
        token = _current.set((self, turn_id))
        try:
            self.open(turn_id, user_id, session_id)
            try:
                yield
            except BaseException as exc:
                if isinstance(exc, asyncio.CancelledError):
                    status: TurnStatus = "cancelled"
                    category = "cancelled"
                else:
                    status = "error"
                    category = (
                        "timeout"
                        if isinstance(exc, TimeoutError)
                        else "invalid_graph_result"
                        if isinstance(exc, (ValueError, TypeError))
                        else "execution_failure"
                    )
                self.update(turn_id, status=status, category=category)
                raise
            finally:
                self.close(turn_id)
        finally:
            _current.reset(token)

    @best_effort
    def open(self, turn_id: str, user_id: str, session_id: str) -> None:
        with self._lock:
            self._active[turn_id] = ActiveTurn(turn_id, user_id, session_id)

    @best_effort
    def update(
        self,
        turn_id: str,
        *,
        route: str | None = None,
        status: TurnStatus | None = None,
        category: str | None = None,
    ) -> None:
        with self._lock:
            turn = self._active.get(turn_id)
            if turn:
                if route is not None:
                    turn.route = route
                if status is not None:
                    turn.status = status
                    turn.failure_category = category

    @best_effort
    def fallback(self, turn_id: str) -> None:
        with self._lock:
            turn = self._active.get(turn_id)
            if turn:
                turn.fallbacks += 1

    @best_effort
    def node(self, turn_id: str, name: str, elapsed_ms: float) -> None:
        with self._lock:
            turn = self._active.get(turn_id)
            if turn:
                turn.nodes.append(NodeObservation(node=name, elapsed_ms=elapsed_ms))

    @best_effort
    def close(self, turn_id: str) -> None:
        with self._lock:
            turn = self._active.pop(turn_id, None)
            if turn is None:
                return
            for run_id, run in list(self._runs.items()):
                if run[0] == turn_id:
                    self._runs.pop(run_id)
                    turn.calls.append(
                        ModelObservation(
                            provider=run[2],
                            model=run[3],
                            node=run[1],
                            elapsed_ms=(time.perf_counter() - run[4]) * 1000,
                            success=False,
                        )
                    )
            try:
                turn.completed = TurnObservation(
                    turn_id=turn.turn_id,
                    user_id=turn.user_id,
                    session_id=turn.session_id,
                    started_at=turn.started_at,
                    completed_at=datetime.now(UTC),
                    elapsed_ms=(time.perf_counter() - turn.start) * 1000,
                    route=turn.route,
                    status=turn.status,
                    failure_category=turn.failure_category,
                    nodes=tuple(turn.nodes),
                    calls=tuple(turn.calls),
                    fallbacks=turn.fallbacks,
                    judgments=tuple(turn.judgments),
                    financial_outcomes=turn.financial_outcomes,
                )
                self._turns.append(turn.completed)
            except Exception:
                self._logger.warning("Turn telemetry unavailable")

    def snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return TelemetrySnapshot(
                process_started_at=self._started_at,
                uptime_seconds=time.perf_counter() - self._start,
                in_progress=len(self._active),
                turns=tuple(self._turns),
                persistence=PersistenceSummary(
                    enabled=self._repository is not None,
                    history_loaded=self._history_loaded,
                    pending_writes=len(self._pending),
                    failed_writes=self._failed_writes,
                    degraded=self._repository is not None
                    and (not self._history_loaded or self._failed_writes > 0),
                ),
            )


def model_identity(
    serialized: dict[str, Any] | None, metadata: dict[str, Any], params: dict[str, Any]
) -> tuple[str, str]:
    model = (
        metadata.get("ls_model_name") or params.get("model") or params.get("model_name")
    )
    kwargs = (serialized or {}).get("kwargs") or {}
    model = model or kwargs.get("model") or kwargs.get("model_name") or "unknown"
    provider = str(metadata.get("ls_provider") or "unknown")
    if provider in {"google_genai", "google_vertexai"}:
        provider = "google"
    return provider, str(model).removeprefix("models/")


def token_usage(message: Any) -> tuple[int | None, int | None]:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict):
        return _count(usage.get("input_tokens")), _count(usage.get("output_tokens"))
    meta = getattr(message, "response_metadata", None) or {}
    usage = meta.get("token_usage") or meta.get("usage") or {}
    return (
        _count(usage.get("prompt_tokens", usage.get("input_tokens"))),
        _count(usage.get("completion_tokens", usage.get("output_tokens"))),
    )


def _count(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


class ModelCollector(BaseCallbackHandler):
    run_inline = True
    raise_error = False

    def __init__(self, store: TurnTelemetry) -> None:
        self._store = store

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        current = _current.get()
        if current is None or current[0] is not self._store:
            return
        provider, model = model_identity(
            serialized, metadata or {}, kwargs.get("invocation_params") or {}
        )
        with self._store._lock:
            if current[1] in self._store._active:
                self._store._runs[run_id] = (
                    current[1],
                    _node.get(),
                    provider,
                    model,
                    time.perf_counter(),
                )

    def _finish(self, run_id: UUID, response: LLMResult | None) -> None:
        with self._store._lock:
            run = self._store._runs.pop(run_id, None)
            if run is None or run[0] not in self._store._active:
                return
            inputs = outputs = None
            model = run[3]
            if response and response.generations and response.generations[0]:
                message = getattr(response.generations[0][0], "message", None)
                inputs, outputs = token_usage(message)
                meta = getattr(message, "response_metadata", None) or {}
                model = str(meta.get("model_name") or meta.get("model") or model)
            self._store._active[run[0]].calls.append(
                ModelObservation(
                    provider=run[2],
                    model=model.removeprefix("models/"),
                    node=run[1],
                    elapsed_ms=(time.perf_counter() - run[4]) * 1000,
                    success=response is not None,
                    input_tokens=inputs,
                    output_tokens=outputs,
                )
            )

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(run_id, response)

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._finish(run_id, None)
