"""Opt-in, synthetic-only model gate; never part of ordinary container CI."""

import json
import math
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from app.application.models.evidence import JudgmentInput
from app.infrastructure.evidence_validator import (
    MODEL,
    RUBRIC_VERSION,
    JevEvidenceValidator,
)
from app.infrastructure.settings import settings

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


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
        validator = JevEvidenceValidator(client, key, lambda _: MagicMock())
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
