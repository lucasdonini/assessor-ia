from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

type Outcome = Literal["ok", "blocked", "error", "cancelled"]


@dataclass(frozen=True, slots=True)
class NodeObservation:
    name: str
    elapsed_ms: float
    status: Outcome


@dataclass(frozen=True, slots=True)
class ModelObservation:
    run_id: str
    node: str
    provider: str
    model: str
    started_at: datetime
    ended_at: datetime
    elapsed_ms: float
    status: Outcome
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    fallback: bool


@dataclass(frozen=True, slots=True)
class TurnObservation:
    turn_id: str
    user_id: str
    session_id: str
    started_at: datetime
    ended_at: datetime
    elapsed_ms: float
    route: str
    status: Outcome
    reason: str | None
    nodes: tuple[NodeObservation, ...]
    attempts: tuple[ModelObservation, ...]
    fallbacks: int
    capture_complete: bool
    detail_truncated: bool


@dataclass(frozen=True, slots=True)
class ObservationSnapshot:
    process_id: str
    process_started_at: datetime
    snapshot_at: datetime
    uptime_seconds: float
    capacity: int
    turns: tuple[TurnObservation, ...]
    in_flight: int


@dataclass(frozen=True, slots=True)
class UsageTotals:
    input_tokens: int
    output_tokens: int
    known_cost_usd: float
    usage_complete: bool
    cost_complete: bool


@dataclass(frozen=True, slots=True)
class ModelGroup:
    provider: str
    model: str
    attempts: int
    errors: int
    successful_latency_mean_ms: float | None
    usage: UsageTotals


@dataclass(frozen=True, slots=True)
class RouteGroup:
    route: str
    turns: int
    errors: int
    latency_mean_ms: float
    usage: UsageTotals


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    turn_id: str
    timestamp: datetime
    value: float


@dataclass(frozen=True, slots=True)
class MonitorWindow:
    process_id: str
    process_started_at: datetime
    snapshot_at: datetime
    uptime_seconds: float
    capacity: int
    sample_size: int
    first_completion: datetime | None
    last_completion: datetime | None
    scope: str = "graph_turn"


@dataclass(frozen=True, slots=True)
class SloMetrics:
    p95_limit_ms: int
    error_rate_limit: float
    sample_size: int
    ok: bool | None


@dataclass(frozen=True, slots=True)
class MonitorSummary:
    turns: int
    eligible_turns: int
    errors: int
    blocked: int
    cancelled: int
    in_flight: int
    latency_mean_ms: float | None
    latency_p95_ms: float | None
    error_rate: float | None
    fallbacks: int
    most_used_model: str | None
    usage: UsageTotals


@dataclass(frozen=True, slots=True)
class MonitoringResult:
    window: MonitorWindow
    slo: SloMetrics
    summary: MonitorSummary
    turns: tuple[TurnObservation, ...]
    by_model: tuple[ModelGroup, ...]
    by_route: tuple[RouteGroup, ...]
    latency_series: tuple[SeriesPoint, ...]
    cost_series: tuple[SeriesPoint, ...]
