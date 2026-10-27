import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import httpx
import pytest

from app.application.models.evidence import JudgmentInput
from app.application.models.observability import TurnObservation
from app.infrastructure.clock import FixedClock
from app.infrastructure.evidence_validator import JevEvidenceValidator
from app.infrastructure.observability import TurnTelemetry


def response(choice="apoiada", noul=0.9):
    return {
        "model": "jev-1.14.0",
        "answers": {
            "veredito": {"type": "choice", "choice": choice},
            "apoiada": {"type": "noul", "noul": noul},
        },
        "usage": {"input_tokens": 30, "output_tokens": 2},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["command", "reply"])
async def test_stage_question_and_structured_command_have_explicit_reference_time(
    stage,
):
    async def handler(request):
        body = json.loads(request.content)
        instructions = body["questions"]["veredito"]["instructions"]
        if stage == "command":
            assert "ANTES de gravar" in instructions
            assert body["state"]["candidate"]["amount"] == 120
        else:
            assert "Avalie a resposta" in instructions
            assert body["state"]["candidate"] == "Você gastou 120 reais."
        assert body["state"]["reference_time"] == "2026-10-27T09:00:00-03:00"
        return httpx.Response(200, json=response())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await JevEvidenceValidator(
            client,
            "key",
            lambda _: MagicMock(),
            clock=FixedClock(
                datetime(2026, 10, 27, 12, tzinfo=timezone.utc), "America/Sao_Paulo"
            ),
        ).validate(
            JudgmentInput(
                stage=stage,
                statements=("120 reais",),
                candidate='{"amount":120}'
                if stage == "command"
                else "Você gastou 120 reais.",
            )
        )
    assert result.approved


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "choice,score,approved",
    [
        ("apoiada", 0.70, True),
        ("apoiada", 0.699, False),
        ("parcial", 0.99, False),
        ("sem_apoio", 1, False),
        ("unknown", 1, False),
        ("apoiada", True, False),
        ("apoiada", "0.9", False),
        ("apoiada", None, False),
        ("apoiada", -0.1, False),
        ("apoiada", 1.1, False),
    ],
)
async def test_strict_decision(choice, score, approved):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response(choice, score))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        judge = JevEvidenceValidator(client, "synthetic-key", lambda _: MagicMock())
        result = await judge.validate(
            JudgmentInput(
                stage="reply",
                statements=("Oi",),
                candidate="Olá",
            )
        )
    assert result.approved is approved
    assert len(calls) == 1
    assert '"veredito"' in calls[0].content.decode()
    assert '"apoiada"' in calls[0].content.decode()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 422, 429, 500, 529])
async def test_http_failure_is_bounded_no_retry(status):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(status, text="private error")

    logger = MagicMock()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await JevEvidenceValidator(client, "key", lambda _: logger).validate(
            JudgmentInput(stage="reply", statements=(), candidate="secret text")
        )
    assert not result.approved
    assert len(calls) == 1
    assert "private error" not in str(logger.mock_calls)
    assert "secret text" not in str(logger.mock_calls)


@pytest.mark.asyncio
async def test_missing_key_and_oversized_input_make_no_request():
    async def handler(request):
        pytest.fail("Must not send request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for key, text, reason in [
            ("", "Olá", "missing_key"),
            ("key", "á" * 24000, "input_too_large"),
        ]:
            result = await JevEvidenceValidator(
                client, key, lambda _: MagicMock()
            ).validate(JudgmentInput(stage="reply", statements=(), candidate=text))
            assert result.reason == reason


@pytest.mark.asyncio
async def test_cancellation_propagates():
    async def handler(request):
        raise asyncio.CancelledError

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(asyncio.CancelledError):
            await JevEvidenceValidator(client, "key", lambda _: MagicMock()).validate(
                JudgmentInput(stage="reply", statements=(), candidate="Olá")
            )


@pytest.mark.asyncio
async def test_no_usage_required_and_pii_is_consistent():
    async def handler(request):
        text = request.content.decode()
        assert "person@example.com" not in text
        assert "4000-1234" in text
        body = response()
        body.pop("usage")
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await JevEvidenceValidator(
            client, "key", lambda _: MagicMock()
        ).validate(
            JudgmentInput(
                stage="reply",
                statements=("person@example.com",),
                candidate="Suporte: (11) 4000-1234",
                evidence=[{"tool": "faq_rag", "text": "(11) 4000-1234"}],
            )
        )
    assert result.approved


@pytest.mark.asyncio
async def test_metadata_only_telemetry_and_old_document_compatibility():
    store = TurnTelemetry(lambda _: MagicMock())

    async def handler(request):
        return httpx.Response(200, json=response("sem_apoio", 0.2))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with store.turn("turn", "owner", "session"):
            await JevEvidenceValidator(
                client, "PRIVATE_KEY", lambda _: MagicMock()
            ).validate(
                JudgmentInput(
                    stage="reply",
                    statements=("PRIVATE_QUESTION",),
                    candidate="PRIVATE_ANSWER",
                    evidence=[{"text": "PRIVATE_EVIDENCE"}],
                )
            )
    turn = store.snapshot().turns[0]
    assert turn.status == "blocked"
    assert turn.calls[0].provider == "typesafe"
    assert turn.calls[0].success
    assert turn.judgments[0].noul == 0.2
    assert "PRIVATE_" not in turn.model_dump_json()
    legacy = turn.model_dump(exclude={"judgments", "financial_outcomes"})
    assert TurnObservation.model_validate(legacy).judgments == ()
