from typing import Any, ClassVar

from langchain_core.messages import AIMessage

from app.application.models.evidence import SAFE_REPLY, JudgmentInput
from app.application.ports.evidence_validator import EvidenceValidator
from app.infrastructure.agents._core.contracts.agent_node import AgentNode
from app.infrastructure.agents._core.evidence import current_evidence
from app.infrastructure.agents._core.state import GraphState, GraphStateKeys
from app.infrastructure.agents.tools.agenda import agenda_evidence, creation_message


def receipt() -> str | None:
    agenda = agenda_evidence().writes
    if agenda:
        return "\n\n".join(creation_message(item) for item in agenda)
    current = current_evidence()
    if current and current.financial.receipts:
        return "\n\n".join(current.financial.receipts)
    return None


class EvidenceJudgeNode(AgentNode):
    name: ClassVar[str] = "evidence_judge"

    def __init__(self, validator: EvidenceValidator) -> None:
        self._validator = validator

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        content = receipt()
        if content is None:
            current = current_evidence()
            content = state["messages"][-1].text
            result = await self._validator.validate(
                JudgmentInput(
                    stage="reply",
                    candidate=content,
                    statements=current.financial.statements if current else (),
                    evidence=current.tools if current else [],
                )
            )
            if not result.approved:
                content = SAFE_REPLY
        return {
            GraphStateKeys.MESSAGES: [AIMessage(content=content)],
            GraphStateKeys.CALLED_AGENTS: [self.name],
        }
