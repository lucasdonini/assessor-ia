from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from math import ceil

from app.application.models.observability import (
    SLO,
    CallSummary,
    ModelObservation,
    ModelSummary,
    MonitorSnapshot,
    RouteSummary,
    SeriesPoint,
    ServiceSummary,
    TurnObservation,
    TurnSummary,
    Usage,
)
from app.application.ports.observability import TelemetryReader

# Standard USD / million tokens, verified 2026-10-26:
# https://ai.google.dev/gemini-api/docs/pricing
# https://console.groq.com/docs/models
# Qwen is intentionally unpriced: no verified Groq rate was established.
PRICES = {
    ("google", "gemini-2.5-flash"): (Decimal("0.30"), Decimal("2.50")),
    ("groq", "openai/gpt-oss-120b"): (Decimal("0.15"), Decimal("0.60")),
}


@dataclass(frozen=True, slots=True)
class MonitorAccess:
    emails: tuple[str, ...] = ()

    def allows(self, authenticated_email: str) -> bool:
        return authenticated_email.strip().casefold() in self.emails


def percentile95(values: Sequence[float]) -> float | None:
    return sorted(values)[ceil(len(values) * 0.95) - 1] if values else None


def summarize_usage(calls: Sequence[ModelObservation], fallbacks: int = 0) -> Usage:
    cost = Decimal(0)
    missing = unpriced = inputs = outputs = 0
    models: Counter[str] = Counter()
    for call in calls:
        price = PRICES.get((call.provider, call.model))
        if price is None:
            unpriced += 1
        inputs += call.input_tokens or 0
        outputs += call.output_tokens or 0
        if call.input_tokens is None or call.output_tokens is None:
            missing += 1
        elif price is not None:
            cost += (
                call.input_tokens * price[0] + call.output_tokens * price[1]
            ) / Decimal(1_000_000)
        if call.success:
            models[call.model] += 1
    successes = sum(call.success for call in calls)
    return Usage(
        attempts=len(calls),
        successes=successes,
        failures=len(calls) - successes,
        input_tokens=inputs,
        output_tokens=outputs,
        total_tokens=inputs + outputs,
        estimated_cost_usd=cost,
        missing_usage_calls=missing,
        unpriced_calls=unpriced,
        cost_complete=missing == 0 and unpriced == 0,
        fallbacks=fallbacks,
        most_used_model=min(models, key=lambda name: (-models[name], name))
        if models
        else None,
    )


class MonitorService:
    def __init__(self, reader: TelemetryReader) -> None:
        self._reader = reader

    def snapshot(self) -> MonitorSnapshot:
        snapshot = self._reader.snapshot()
        turns = snapshot.turns
        calls = [call for turn in turns for call in turn.calls]
        latencies = [turn.elapsed_ms for turn in turns]
        errors = sum(turn.status in {"error", "cancelled"} for turn in turns)
        rate = errors / len(turns) if turns else None
        p95 = percentile95(latencies)
        ok = (
            p95 <= 8000 and rate <= 0.05
            if p95 is not None and rate is not None
            else None
        )
        by_model: defaultdict[tuple[str, str], list[ModelObservation]] = defaultdict(
            list
        )
        by_route: defaultdict[str, list[TurnObservation]] = defaultdict(list)
        series: list[SeriesPoint] = []
        cumulative = Decimal(0)
        for turn in turns:
            by_route[turn.route].append(turn)
            cumulative += summarize_usage(turn.calls).estimated_cost_usd
            series.append(
                SeriesPoint(
                    turn_id=turn.turn_id,
                    started_at=turn.started_at,
                    latency_ms=turn.elapsed_ms,
                    cumulative_cost_usd=cumulative,
                )
            )
        for call in calls:
            by_model[(call.provider, call.model)].append(call)
        return MonitorSnapshot(
            generated_at=datetime.now(UTC),
            process_started_at=snapshot.process_started_at,
            uptime_seconds=snapshot.uptime_seconds,
            window_turns=len(turns),
            persistence=snapshot.persistence,
            retention="mongo_window"
            if snapshot.persistence.enabled
            else "process_window",
            service=ServiceSummary(
                completed_turns=len(turns),
                in_progress=snapshot.in_progress,
                blocked_turns=sum(turn.status == "blocked" for turn in turns),
                error_turns=sum(turn.status == "error" for turn in turns),
                cancelled_turns=sum(turn.status == "cancelled" for turn in turns),
                average_latency_ms=sum(latencies) / len(turns) if turns else None,
                p95_latency_ms=p95,
                error_rate=rate,
            ),
            slo=SLO(
                ok=ok,
                state="no_data"
                if ok is None
                else "within_target"
                if ok
                else "breached",
            ),
            usage=summarize_usage(calls, sum(turn.fallbacks for turn in turns)),
            turns=tuple(
                TurnSummary(
                    **turn.model_dump(exclude={"calls"}),
                    calls=tuple(
                        CallSummary(**call.model_dump(), usage=summarize_usage([call]))
                        for call in turn.calls
                    ),
                    usage=summarize_usage(turn.calls, turn.fallbacks),
                )
                for turn in reversed(turns)
            ),
            models=tuple(
                ModelSummary(
                    provider=provider, model=model, usage=summarize_usage(group)
                )
                for (provider, model), group in sorted(by_model.items())
            ),
            routes=tuple(
                RouteSummary(
                    route=route,
                    turns=len(group),
                    average_latency_ms=sum(t.elapsed_ms for t in group) / len(group),
                    p95_latency_ms=percentile95([t.elapsed_ms for t in group]) or 0,
                    errors=sum(t.status in {"error", "cancelled"} for t in group),
                    usage=summarize_usage(
                        [call for t in group for call in t.calls],
                        sum(t.fallbacks for t in group),
                    ),
                )
                for route, group in sorted(by_route.items())
            ),
            series=tuple(series),
        )
