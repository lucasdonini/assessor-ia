from typing import Protocol

from app.application.models.evidence import Judgment, JudgmentInput


class EvidenceValidator(Protocol):
    async def validate(self, request: JudgmentInput) -> Judgment: ...
