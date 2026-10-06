from dataclasses import replace
from unittest.mock import MagicMock

from app.infrastructure.observability import InMemoryObservability
from app.services.monitoring_service import MonitoringService


def fixture_snapshot():
    collector = InMemoryObservability()
    for index in range(20):
        with collector.turn(str(index), "u", "s"):
            if index == 0:
                collector.classify("error", "classifier_unavailable")
            elif index == 1:
                collector.classify("blocked", "prompt_injection")
    snapshot = collector.snapshot("u")
    turns = tuple(
        replace(t, elapsed_ms=8000 if i == 18 else i * 100)
        for i, t in enumerate(snapshot.turns)
    )
    return replace(snapshot, turns=turns)


def test_exact_nearest_rank_inclusive_thresholds_and_denominator():
    snapshot = fixture_snapshot()
    # 19 values <= 1900 and one outlier: p95 is 1900, not the maximum.
    reader = MagicMock()
    reader.snapshot.return_value = snapshot
    result = MonitoringService(reader).get_monitor("u")
    assert result.summary.latency_p95_ms == 1900
    assert result.summary.error_rate == 0.05
    assert result.summary.blocked == 1
    assert result.slo.ok is True
    reader.snapshot.assert_called_once_with("u")
    turns = tuple(replace(t, elapsed_ms=8000) for t in snapshot.turns)
    reader.snapshot.return_value = replace(snapshot, turns=turns)
    assert MonitoringService(reader).get_monitor("u").slo.ok is True
    reader.snapshot.return_value = replace(
        snapshot, turns=tuple(replace(t, elapsed_ms=8001) for t in turns)
    )
    assert MonitoringService(reader).get_monitor("u").slo.ok is False
    reader.snapshot.return_value = replace(
        snapshot,
        turns=(
            replace(turns[0], status="error"),
            replace(turns[1], status="error"),
            *turns[2:],
        ),
    )
    assert MonitoringService(reader).get_monitor("u").slo.ok is False


def test_empty_cancelled_and_foreign_turns_are_not_slo_samples():
    collector = InMemoryObservability()
    service = MonitoringService(collector)
    assert service.get_monitor("u").slo.ok is None
    with collector.turn("t", "u", "s"):
        collector.classify("cancelled")
    result = service.get_monitor("u")
    assert result.summary.cancelled == 1
    assert result.summary.eligible_turns == 0
    assert result.slo.ok is None
    reader = MagicMock()
    reader.snapshot.return_value = collector.snapshot("u")
    assert MonitoringService(reader).get_monitor("other").summary.turns == 0
