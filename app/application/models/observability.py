from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

TurnStatus = Literal["ok", "blocked", "error", "cancelled"]


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True)


class NodeObservation(Observation):
    node: str
    elapsed_ms: float


class ModelObservation(Observation):
    provider: str
    model: str
    node: str
    elapsed_ms: float
    success: bool
    input_tokens: int | None = None
    output_tokens: int | None = None


class TurnObservation(Observation):
    turn_id: str
    user_id: str
    session_id: str
    started_at: datetime
    elapsed_ms: float
    route: str
    status: TurnStatus
    failure_category: str | None = None
    nodes: tuple[NodeObservation, ...] = ()
    calls: tuple[ModelObservation, ...] = ()
    fallbacks: int = 0


class TelemetrySnapshot(Observation):
    process_started_at: datetime
    uptime_seconds: float
    in_progress: int
    turns: tuple[TurnObservation, ...]


class Usage(Observation):
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: Decimal = Decimal(0)
    missing_usage_calls: int = 0
    unpriced_calls: int = 0
    cost_complete: bool = True
    fallbacks: int = 0
    most_used_model: str | None = None


class ModelSummary(Observation):
    provider: str
    model: str
    usage: Usage


class RouteSummary(Observation):
    route: str
    turns: int
    average_latency_ms: float
    p95_latency_ms: float
    errors: int
    usage: Usage


class CallSummary(ModelObservation):
    usage: Usage


class TurnSummary(TurnObservation):
    calls: tuple[CallSummary, ...] = ()
    usage: Usage


class SeriesPoint(Observation):
    turn_id: str
    started_at: datetime
    latency_ms: float
    cumulative_cost_usd: Decimal


class ServiceSummary(Observation):
    completed_turns: int
    in_progress: int
    blocked_turns: int
    error_turns: int
    cancelled_turns: int
    average_latency_ms: float | None
    p95_latency_ms: float | None
    error_rate: float | None


class SLO(Observation):
    latency_limit_ms: int = 8000
    error_rate_limit: float = 0.05
    ok: bool | None
    state: Literal["no_data", "within_target", "breached"]


class MonitorSnapshot(Observation):
    generated_at: datetime
    process_started_at: datetime
    uptime_seconds: float
    window_limit: int = 50
    window_turns: int
    scope: Literal["operator_global"] = "operator_global"
    retention: Literal["process_window"] = "process_window"
    price_catalog: str = "2026-10-26-standard-usd"
    service: ServiceSummary
    slo: SLO
    usage: Usage
    turns: tuple[TurnSummary, ...]
    models: tuple[ModelSummary, ...]
    routes: tuple[RouteSummary, ...]
    series: tuple[SeriesPoint, ...]
