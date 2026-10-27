from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from pydantic import BaseModel, JsonValue

from app.application.models.evidence import FinancialExecution


@dataclass
class TurnEvidence:
    financial: FinancialExecution
    tools: list[dict[str, JsonValue]] = field(default_factory=list)


_current: ContextVar[TurnEvidence | None] = ContextVar("evidence", default=None)


@contextmanager
def evidence_execution(
    user_id: UUID, statements: tuple[str, ...]
) -> Iterator[TurnEvidence]:
    evidence = TurnEvidence(FinancialExecution(user_id, statements))
    token = _current.set(evidence)
    try:
        yield evidence
    finally:
        _current.reset(token)


def current_evidence() -> TurnEvidence | None:
    return _current.get()


def financial_execution() -> FinancialExecution | None:
    current = _current.get()
    return current.financial if current else None


def record_tool(name: str, args: dict[str, object], result: BaseModel) -> None:
    current = _current.get()
    if current is not None:
        # Pydantic serializes domain models, dates and enums consistently.
        from pydantic import TypeAdapter

        current.tools.append(
            {
                "id": str(uuid4()),
                "tool": name,
                "arguments": TypeAdapter(dict[str, JsonValue]).validate_python(
                    TypeAdapter(dict[str, object]).dump_python(args, mode="json")
                ),
                "result": result.model_dump(mode="json"),
            }
        )
