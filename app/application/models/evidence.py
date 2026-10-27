import asyncio
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, JsonValue

SAFE_REPLY = "Não tenho evidência para afirmar isso."


class JudgmentInput(BaseModel):
    stage: Literal["command", "reply"]
    statements: tuple[str, ...]
    candidate: str
    evidence: list[dict[str, JsonValue]] = []


class Judgment(BaseModel):
    approved: bool = False
    reason: str
    choice: str | None = None
    noul: float | None = None
    model: str | None = None


@dataclass
class FinancialExecution:
    user_id: UUID
    statements: tuple[str, ...]
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    results: dict[str, object] = field(default_factory=dict)
    receipts: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)
    stopped: bool = False
