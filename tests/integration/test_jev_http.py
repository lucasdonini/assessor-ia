import os
import time
from unittest.mock import MagicMock

import httpx
import pytest

from app.application.models.evidence import JudgmentInput
from app.infrastructure.evidence_validator import JevEvidenceValidator

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize(
    "mode,approved",
    [
        ("approve", True),
        ("reject", False),
        ("partial", False),
        ("low", False),
        ("malformed", False),
        ("rate", False),
        ("error", False),
        ("hang", False),
    ],
)
async def test_real_adapter_against_postman(mode, approved):
    base = os.environ.get("JEV_SIMULATION_URL")
    if not base:
        pytest.skip(
            "Start the documented Postman simulation and set JEV_SIMULATION_URL"
        )
    async with httpx.AsyncClient() as client:
        judge = JevEvidenceValidator(
            client,
            "synthetic-key",
            lambda _: MagicMock(),
            url=f"{base}/{mode}/v1/systemone",
        )
        start = time.perf_counter()
        result = await judge.validate(
            JudgmentInput(
                stage="reply",
                statements=("Quanto gastei?",),
                candidate="Você gastou R$ 120.",
                evidence=[{"tool": "search_transactions", "amount": 120}],
            )
        )
    assert result.approved is approved
    assert time.perf_counter() - start < 5.8
