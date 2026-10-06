from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from math import ceil
from statistics import mean

from app.application.models.observability import (
    ModelGroup,
    ModelObservation,
    MonitoringResult,
    MonitorSummary,
    MonitorWindow,
    RouteGroup,
    SeriesPoint,
    SloMetrics,
    TurnObservation,
    UsageTotals,
)
from app.application.ports.observability import ObservationReader


def usage_totals(
    attempts: Sequence[ModelObservation], *, capture_complete: bool = True
) -> UsageTotals:
    return UsageTotals(
        sum(item.input_tokens or 0 for item in attempts),
        sum(item.output_tokens or 0 for item in attempts),
        float(sum((item.cost_usd or Decimal(0) for item in attempts), Decimal(0))),
        capture_complete
        and all(
            item.input_tokens is not None and item.output_tokens is not None
            for item in attempts
        ),
        capture_complete and all(item.cost_usd is not None for item in attempts),
    )


class MonitoringService:
    def __init__(self, reader: ObservationReader) -> None:
        self._reader = reader

    def get_monitor(self, user_id: str) -> MonitoringResult:
        snapshot = self._reader.snapshot(user_id)
        # Defense in depth: the aggregation boundary also enforces ownership.
        turns = tuple(turn for turn in snapshot.turns if turn.user_id == user_id)
        eligible = [turn for turn in turns if turn.status != "cancelled"]
        errors = sum(turn.status == "error" for turn in eligible)
        rate = errors / len(eligible) if eligible else None
        latencies = sorted(turn.elapsed_ms for turn in eligible)
        p95 = latencies[ceil(0.95 * len(latencies)) - 1] if latencies else None
        attempts = [attempt for turn in turns for attempt in turn.attempts]
        complete = all(turn.capture_complete for turn in turns)
        models: dict[tuple[str, str], list[ModelObservation]] = defaultdict(list)
        routes: dict[str, list[TurnObservation]] = defaultdict(list)
        for attempt in attempts:
            models[(attempt.provider, attempt.model)].append(attempt)
        for turn in turns:
            routes[turn.route].append(turn)
        by_model = tuple(
            ModelGroup(
                provider,
                model,
                len(items),
                sum(i.status == "error" for i in items),
                mean(successful)
                if (successful := [i.elapsed_ms for i in items if i.status == "ok"])
                else None,
                usage_totals(items, capture_complete=complete),
            )
            for (provider, model), items in sorted(models.items())
        )
        by_route = tuple(
            RouteGroup(
                route,
                len(items),
                sum(i.status == "error" for i in items),
                mean(i.elapsed_ms for i in items),
                usage_totals(
                    [a for i in items for a in i.attempts],
                    capture_complete=all(i.capture_complete for i in items),
                ),
            )
            for route, items in sorted(routes.items())
        )
        most_used = (
            min(models, key=lambda key: (-len(models[key]), key)) if models else None
        )
        running_cost = Decimal(0)
        cost_series: list[SeriesPoint] = []
        for turn in turns:
            running_cost += sum(
                (item.cost_usd or Decimal(0) for item in turn.attempts), Decimal(0)
            )
            cost_series.append(
                SeriesPoint(turn.turn_id, turn.ended_at, float(running_cost))
            )
        return MonitoringResult(
            MonitorWindow(
                snapshot.process_id,
                snapshot.process_started_at,
                snapshot.snapshot_at,
                snapshot.uptime_seconds,
                snapshot.capacity,
                len(turns),
                turns[0].ended_at if turns else None,
                turns[-1].ended_at if turns else None,
            ),
            SloMetrics(
                8000,
                0.05,
                len(eligible),
                p95 <= 8000 and rate <= 0.05
                if p95 is not None and rate is not None
                else None,
            ),
            MonitorSummary(
                len(turns),
                len(eligible),
                errors,
                sum(i.status == "blocked" for i in turns),
                sum(i.status == "cancelled" for i in turns),
                snapshot.in_flight,
                mean(latencies) if latencies else None,
                p95,
                rate,
                sum(i.fallbacks for i in turns),
                most_used[1] if most_used else None,
                usage_totals(attempts, capture_complete=complete),
            ),
            turns,
            by_model,
            by_route,
            tuple(SeriesPoint(i.turn_id, i.ended_at, i.elapsed_ms) for i in turns),
            tuple(cost_series),
        )
