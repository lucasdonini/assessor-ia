"""Opt-in, synthetic-only model gate; never part of ordinary container CI."""

import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.application.models.evidence import FinancialExecution, JudgmentInput
from app.domain.model.transaction import Transaction
from app.infrastructure.clock import FixedClock
from app.infrastructure.evidence_validator import (
    MODEL,
    RUBRIC_VERSION,
    JevEvidenceValidator,
)
from app.infrastructure.settings import settings
from app.services.transaction_service import TransactionService
from tests.user_identity import TEST_USER_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("followups", [("Sim",), ("Sim", "120", "120")])
async def test_live_production_command_after_confirmation(followups):
    if os.environ.get("RUN_JEV_EVALUATION") != "1":
        pytest.skip("Opt in with RUN_JEV_EVALUATION=1 and an own TYPESAFE_API_KEY")
    key = settings.typesafe_api_key.get_secret_value()
    if not key.strip():
        pytest.fail("Configure an own TYPESAFE_API_KEY")
    original = "Comprei uma camisa na Zara por 120 reais"
    proposed = Transaction(user_id=TEST_USER_ID, amount=120, source_text="Sim")
    repo = AsyncMock()
    repo.add_transaction.return_value = proposed
    async with httpx.AsyncClient() as client:
        validator = JevEvidenceValidator(client, key, lambda _: MagicMock())
        service = TransactionService(repo, lambda _: MagicMock(), validator)
        await service.add_transaction(
            proposed,
            user_id=TEST_USER_ID,
            execution=FinancialExecution(TEST_USER_ID, (original, *followups)),
        )
    repo.add_transaction.assert_awaited_once()
    assert repo.add_transaction.call_args.args[0].source_text == original


async def test_frozen_portuguese_evaluation():
    if os.environ.get("RUN_JEV_EVALUATION") != "1":
        pytest.skip("Opt in with RUN_JEV_EVALUATION=1 and an own TYPESAFE_API_KEY")
    key = settings.typesafe_api_key.get_secret_value()
    if not key.strip():
        pytest.fail("Configure an own TYPESAFE_API_KEY; no classroom key is used")
    path = (
        Path(__file__).resolve().parents[2]
        / "specs/004-evidence-validation/evaluation-cases.json"
    )
    cases = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    async with httpx.AsyncClient() as client:
        validator = JevEvidenceValidator(
            client,
            key,
            lambda _: MagicMock(),
            clock=FixedClock(
                datetime(2026, 10, 27, 12, tzinfo=timezone.utc), "America/Sao_Paulo"
            ),
        )
        for case in cases:
            start = time.perf_counter()
            result = await validator.validate(
                JudgmentInput(
                    stage=case["stage"],
                    statements=tuple(case["statements"]),
                    candidate=case["candidate"],
                    evidence=case["evidence"],
                )
            )
            rows.append(
                {
                    "id": case["id"],
                    "split": case["split"],
                    "expected": case["expected"],
                    "approved": result.approved,
                    "reason": result.reason,
                    "choice": result.choice,
                    "noul": result.noul,
                    "model": result.model,
                    "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
                }
            )
    false_approvals = sum(row["approved"] and not row["expected"] for row in rows)
    true_approvals = sum(row["approved"] and row["expected"] for row in rows)
    warm = sorted(row["elapsed_ms"] for row in rows[1:])
    p95 = warm[math.ceil(len(warm) * 0.95) - 1]
    print(
        json.dumps(
            {
                "model": MODEL,
                "rubric": RUBRIC_VERSION,
                "rows": rows,
                "false_approvals": false_approvals,
                "true_approvals": true_approvals,
                "warm_p95_ms": p95,
            },
            ensure_ascii=False,
        )
    )
    assert len(rows) == 24
    assert all(row["reason"] in {"approved", "unsupported"} for row in rows)
    assert false_approvals == 0
    assert true_approvals >= 10
    assert p95 <= 2000
