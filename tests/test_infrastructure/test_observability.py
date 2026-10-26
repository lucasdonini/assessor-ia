import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app.application.models.observability import (
    ModelObservation,
    TelemetrySnapshot,
    TurnObservation,
)
from app.infrastructure.observability import (
    TurnTelemetry,
    observe_block,
    observe_fallback,
    observe_node,
    observe_route,
    token_usage,
)
from app.infrastructure.settings import PydanticSettings
from app.infrastructure.tracing import PrivateTracing, private_run_ops
from app.services.monitor_service import (
    MonitorAccess,
    MonitorService,
    percentile95,
    summarize_usage,
)


@pytest.fixture
def store():
    return TurnTelemetry(lambda _: MagicMock())


def record_model(store, *, usage=True, success=True):
    run_id = uuid4()
    store.callback.on_chat_model_start(
        {},
        [],
        run_id=run_id,
        metadata={"ls_provider": "groq", "ls_model_name": "openai/gpt-oss-120b"},
    )
    if success:
        message = AIMessage(
            content="PRIVATE_SENTINEL",
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            }
            if usage
            else None,
        )
        store.callback.on_llm_end(
            LLMResult(generations=[[ChatGeneration(message=message)]]), run_id=run_id
        )
    else:
        store.callback.on_llm_error(ValueError("PRIVATE_SENTINEL"), run_id=run_id)
    return run_id


def test_lifecycle_callback_retention_and_unknown_usage(store):
    record_model(store)
    assert not store.snapshot().turns
    for index in range(51):
        with store.turn(str(index), "owner", "session"):
            assert store.snapshot().in_progress == 1
            with observe_node("financial"):
                observe_route("financial")
                run_id = record_model(store, usage=index != 50)
    snapshot = store.snapshot()
    assert snapshot.in_progress == 0
    assert len(snapshot.turns) == 50
    assert snapshot.turns[0].turn_id == "1"
    assert snapshot.turns[-1].calls[0].node == "financial"
    assert snapshot.turns[-1].calls[0].input_tokens is None
    store.close("50")
    store.callback.on_llm_error(ValueError(), run_id=run_id)
    assert store.snapshot() == snapshot or len(store.snapshot().turns) == 50
    assert not store._runs
    assert "PRIVATE_SENTINEL" not in snapshot.model_dump_json()
    assert not TurnTelemetry(lambda _: MagicMock()).snapshot().turns


@pytest.mark.parametrize(
    "reason,status,category",
    [
        ("prompt_injection", "blocked", None),
        ("classificador_indisponivel", "error", "classifier_unavailable"),
        ("classificacao_indeterminada", "error", "classification_indeterminate"),
    ],
)
def test_guardrail_outcomes(store, reason, status, category):
    with store.turn("turn", "owner", "session"):
        observe_block(reason)
    turn = store.snapshot().turns[0]
    assert (turn.status, turn.failure_category, turn.route) == (
        status,
        category,
        "blocked",
    )


@pytest.mark.asyncio
async def test_interleaved_contexts_errors_and_cancellation(store):
    ready = asyncio.Event()

    async def first():
        with store.turn("a", "owner-a", "session"):
            with observe_node("financial"):
                ready.set()
                await asyncio.sleep(0.01)
                record_model(store)
                observe_fallback()
                raise TimeoutError("PRIVATE_SENTINEL")

    async def second():
        await ready.wait()
        with store.turn("b", "owner-b", "session"):
            with observe_node("faq"):
                record_model(store, success=False)
                raise asyncio.CancelledError()

    results = await asyncio.gather(first(), second(), return_exceptions=True)
    assert isinstance(results[0], TimeoutError)
    assert isinstance(results[1], asyncio.CancelledError)
    turns = {turn.turn_id: turn for turn in store.snapshot().turns}
    assert turns["a"].status == "error"
    assert turns["a"].fallbacks == 1
    assert turns["a"].calls[0].node == "financial"
    assert turns["b"].status == "cancelled"
    assert turns["b"].calls[0].node == "faq"
    assert turns["b"].fallbacks == 0
    assert store.snapshot().in_progress == 0
    assert not store._runs


def test_usage_prices_unknowns_and_reasoning_not_double_counted():
    call = ModelObservation(
        provider="google",
        model="gemini-2.5-flash",
        node="financial",
        elapsed_ms=1,
        success=True,
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert summarize_usage([call]).estimated_cost_usd == Decimal("2.80")
    unknown = call.model_copy(update={"model": "qwen/qwen3.6-27b", "provider": "groq"})
    usage = summarize_usage([call, unknown])
    assert usage.unpriced_calls == 1
    assert not usage.cost_complete
    assert usage.estimated_cost_usd == Decimal("2.80")
    assert token_usage(
        AIMessage(
            content="",
            response_metadata={
                "token_usage": {"prompt_tokens": 12, "completion_tokens": 20},
            },
        )
    ) == (12, 20)
    assert token_usage(
        AIMessage(
            content="",
            usage_metadata={
                "input_tokens": 12,
                "output_tokens": 20,
                "total_tokens": 32,
                "output_token_details": {"reasoning": 8},
            },
        )
    ) == (12, 20)


def test_slo_rank_window_groups_and_decimal_wire_format(store):
    assert percentile95([]) is None
    assert percentile95([4, 3, 2, 1]) == 4
    assert percentile95(list(range(1, 21))) == 19
    reader = MagicMock()
    reader.snapshot.return_value = TelemetrySnapshot(
        process_started_at=datetime.now(UTC), uptime_seconds=5, in_progress=1, turns=()
    )
    service = MonitorService(reader)
    assert service.snapshot().slo.state == "no_data"
    turns = tuple(
        TurnObservation(
            turn_id=str(i),
            user_id="owner",
            session_id="session",
            started_at=datetime.now(UTC),
            elapsed_ms=8000,
            route="financial",
            status="error" if i == 0 else "blocked",
        )
        for i in range(20)
    )
    reader.snapshot.return_value = reader.snapshot.return_value.model_copy(
        update={"turns": turns}
    )
    result = service.snapshot()
    assert result.slo.ok is True
    assert result.service.error_rate == 0.05
    assert result.service.p95_latency_ms == 8000
    assert result.turns[0].turn_id == "19"
    assert result.series[0].turn_id == "0"
    assert result.routes[0].turns == 20
    assert json.loads(result.model_dump_json())["usage"]["estimated_cost_usd"] == "0"
    changed = turns[:18] + (turns[18].model_copy(update={"elapsed_ms": 8001}),) * 2
    reader.snapshot.return_value = reader.snapshot.return_value.model_copy(
        update={"turns": changed}
    )
    assert service.snapshot().slo.ok is False


def test_settings_and_operator_email_authority(monkeypatch):
    monkeypatch.setenv("MONITOR_OPERATOR_EMAILS", '[" Admin@Example.com "]')
    settings = PydanticSettings(_env_file=None)
    access = MonitorAccess(settings.monitor_operator_emails)
    assert access.allows("ADMIN@example.COM")
    assert not access.allows("admin+other@example.com")
    assert not MonitorAccess().allows("admin@example.com")
    monkeypatch.setenv("MONITOR_OPERATOR_EMAILS", '["*@example.com"]')
    with pytest.raises(ValueError):
        PydanticSettings(_env_file=None)


def test_outbound_trace_privacy_and_disabled_independence():
    run_id = uuid4()
    raw = {
        "id": run_id,
        "name": "PRIVATE_SENTINEL",
        "inputs": {"secret": "PRIVATE_SENTINEL"},
        "outputs": {"secret": "PRIVATE_SENTINEL"},
        "error": "PRIVATE_SENTINEL",
        "serialized": {"secret": "PRIVATE_SENTINEL"},
        "events": [{"name": "PRIVATE_SENTINEL"}],
        "extra": {
            "metadata": {
                "token": "PRIVATE_SENTINEL",
                "ls_model_name": "PRIVATE_SENTINEL",
                "ls_provider": "groq",
                "turn_id": str(run_id),
            }
        },
    }
    safe = private_run_ops([raw])[0]
    assert safe["id"] == run_id
    assert safe["extra"]["metadata"]["ls_provider"] == "groq"
    assert "PRIVATE_SENTINEL" not in json.dumps(safe, default=str)
    tracer = PrivateTracing(
        enabled=False, api_key="", project="test", logger_factory=lambda _: MagicMock()
    )
    with tracer.scope():
        assert tracer.callbacks() == []
    tracer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_real_guardrail_keeps_safe_response_and_records_failure(store, failure):
    from unittest.mock import AsyncMock

    from langchain_core.messages import HumanMessage

    from app.infrastructure.agents.guardrails.input_guardrail import InputGuardrailNode

    generator = MagicMock()
    generator.generate = AsyncMock(return_value="CATEGORIA: APROVADO")
    if failure:
        generator.generate.side_effect = RuntimeError("PRIVATE_SENTINEL")
    guard = InputGuardrailNode(
        approved_route="router",
        text_generator=generator,
        logger_factory=lambda _: MagicMock(),
    )
    with store.turn("guard", "owner", "session"):
        response = await guard(
            {"messages": [HumanMessage(id="id", content="Qual é o saldo?")]}
        )
    turn = store.snapshot().turns[0]
    assert turn.status == ("error" if failure else "ok")
    if failure:
        assert turn.failure_category == "classifier_unavailable"
        assert "PRIVATE_SENTINEL" not in str(response)


def test_recording_failure_does_not_escape_to_business_code(store, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("PRIVATE_SENTINEL")

    monkeypatch.setattr("app.infrastructure.observability.NodeObservation", unavailable)
    with store.turn("turn", "owner", "session"):
        with observe_node("financial"):
            result = "business result"
    assert result == "business result"
    assert store.snapshot().in_progress == 0
    assert store.snapshot().turns[0].status == "ok"
