from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.application.models.observability import (
    ModelGroup,
    MonitorSummary,
    MonitorWindow,
    NodeObservation,
    Outcome,
    RouteGroup,
    SeriesPoint,
    SloMetrics,
)


class ModelAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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
    cost_usd: float | None
    fallback: bool


class TurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    turn_id: str
    session_id: str
    started_at: datetime
    ended_at: datetime
    elapsed_ms: float
    route: str
    status: Outcome
    reason: str | None
    nodes: tuple[NodeObservation, ...]
    attempts: tuple[ModelAttemptResponse, ...]
    fallbacks: int
    capture_complete: bool
    detail_truncated: bool


class MonitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    window: MonitorWindow
    slo: SloMetrics
    summary: MonitorSummary
    turns: tuple[TurnResponse, ...]
    by_model: tuple[ModelGroup, ...]
    by_route: tuple[RouteGroup, ...]
    latency_series: tuple[SeriesPoint, ...]
    cost_series: tuple[SeriesPoint, ...]
