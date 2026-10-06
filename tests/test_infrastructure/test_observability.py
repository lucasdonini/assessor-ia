import asyncio
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.runnables import RunnableLambda

from app.infrastructure.agents._core.middleware import FallbackOn429Middleware
from app.infrastructure.observability import DETAIL_LIMIT, InMemoryObservability
from app.infrastructure.text_generator import LLMTextGenerator
from app.services.monitoring_service import MonitoringService


def call(collector, *, model="gemini-2.5-flash", provider="google_genai", usage=True):
    run = uuid4()
    collector.on_chat_model_start(
        {},
        [],
        run_id=run,
        metadata={
            "ls_provider": provider,
            "ls_model_name": model,
        },
    )
    message = AIMessage(
        content="PRIVATE RESPONSE",
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        }
        if usage
        else None,
    )
    collector.on_llm_end(
        LLMResult(generations=[[ChatGeneration(message=message)]]), run_id=run
    )
    return run


def test_known_zero_unknown_cost_and_no_content():
    collector = InMemoryObservability()
    with collector.turn("t1", "u", "s"), collector.node("financial"):
        call(collector)
        call(collector, model="unknown")
    result = MonitoringService(collector).get_monitor("u")
    assert result.summary.usage.input_tokens == 20
    assert result.summary.usage.known_cost_usd == pytest.approx(0.000053)
    assert result.summary.usage.usage_complete
    assert not result.summary.usage.cost_complete
    assert result.turns[0].attempts[1].cost_usd is None
    assert "PRIVATE" not in str(asdict(result))
    with collector.turn("t2", "u", "s"):
        collector.classify("blocked", "prompt_injection")
    assert result.summary.errors == 0
    assert MonitoringService(collector).get_monitor("u").turns[1].attempts == ()


def test_missing_usage_errors_eviction_and_late_callback():
    collector = InMemoryObservability(capacity=2)
    with collector.turn("t1", "other", "same"):
        call(collector)
    run = uuid4()
    with pytest.raises(TimeoutError), collector.turn("t2", "u", "same"):
        collector.on_chat_model_start({}, [], run_id=run)
        raise TimeoutError("PRIVATE ERROR")
    with collector.turn("t3", "u", "same"):
        call(collector, usage=False)
    collector.on_llm_error(ValueError("late"), run_id=run)
    snapshot = collector.snapshot("u")
    assert snapshot.in_flight == 0
    assert [t.turn_id for t in snapshot.turns] == ["t2", "t3"]
    assert snapshot.turns[0].reason == "timeout"
    assert not snapshot.turns[0].capture_complete
    assert snapshot.turns[0].attempts[0].input_tokens is None
    assert collector.snapshot("other").turns == ()
    assert (
        not MonitoringService(collector).get_monitor("u").summary.usage.usage_complete
    )
    assert InMemoryObservability().snapshot("u").turns == ()


@pytest.mark.asyncio
async def test_async_nested_runnable_and_direct_generator_propagate():
    collector = InMemoryObservability()
    llm = FakeListChatModel(responses=["reply"])
    generator = LLMTextGenerator(llm)
    agent = create_agent(llm)

    async def invoke(_: str):
        with collector.node("guardrail"):
            await agent.ainvoke({"messages": [("human", "PRIVATE PROMPT")]})
            return await generator.generate("PRIVATE PROMPT")

    nested = RunnableLambda(invoke)
    with collector.turn("trace", "u", "s"):
        assert (
            await nested.ainvoke("input", config={"callbacks": [collector]}) == "reply"
        )
    turn = collector.snapshot("u").turns[0]
    assert len(turn.attempts) == 2
    assert turn.attempts[0].node == "guardrail"
    assert turn.attempts[0].input_tokens is None


@pytest.mark.asyncio
async def test_concurrent_equal_sessions_are_isolated_and_cancellation_cleans():
    collector = InMemoryObservability()
    ready = asyncio.Event()

    async def execute(user):
        with collector.turn(user, user, "same"), collector.node(user):
            ready.set()
            await asyncio.sleep(0)
            assert collector.snapshot(user).in_flight == 1
            call(collector)

    await asyncio.gather(execute("a"), execute("b"))
    assert collector.snapshot("a").turns[0].attempts[0].node == "a"
    assert collector.snapshot("b").turns[0].attempts[0].node == "b"

    async def cancelled():
        with collector.turn("cancel", "a", "same"):
            ready.set()
            await asyncio.Event().wait()

    ready.clear()
    task = asyncio.create_task(cancelled())
    await ready.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert collector.snapshot("a").in_flight == 0
    assert collector.snapshot("a").turns[-1].status == "cancelled"


@pytest.mark.asyncio
async def test_real_fallback_activations_count_attempts_without_turn_error():
    collector = InMemoryObservability()
    error = RuntimeError("PRIVATE")
    error.status_code = 429
    middleware = FallbackOn429Middleware(
        MagicMock(), logger_factory=lambda _: MagicMock(), recorder=collector
    )
    request = MagicMock()
    with collector.turn("t", "u", "s"), collector.node("financial"):
        for _ in range(2):
            await middleware.awrap_model_call(
                request, AsyncMock(side_effect=[error, "ok"])
            )
            call(collector, model="qwen/qwen3.6-27b", provider="groq")
        call(collector)
    turn = collector.snapshot("u").turns[0]
    assert turn.fallbacks == 2
    assert [a.fallback for a in turn.attempts] == [True, True, False]
    assert turn.status == "ok"


def test_duplicate_end_is_ignored_and_detail_is_bounded():
    collector = InMemoryObservability()
    with collector.turn("t", "u", "s"):
        run = call(collector)
        collector.on_llm_error(RuntimeError(), run_id=run)
        for _ in range(DETAIL_LIMIT + 2):
            call(collector)
    turn = collector.snapshot("u").turns[0]
    assert len(turn.attempts) == DETAIL_LIMIT
    assert turn.detail_truncated
    assert not turn.capture_complete
