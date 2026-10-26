import re
from typing import Any, ClassVar, Final

from langchain_core.messages import AIMessage

from app.application.ports.logger import Logger, LoggerFactory
from app.application.ports.text_generator import TextGenerator
from app.infrastructure.agents._core.contracts.agent_node import AgentNode
from app.infrastructure.agents._core.state import GraphState, GraphStateKeys
from app.infrastructure.agents.guardrails.result import GuardrailResult
from app.infrastructure.agents.tools.agenda import agenda_evidence, creation_message

from .anonymization import deanonymize_output
from .anonymization_config import PII
from .guardrails_prompts import COMPLIANCE_PROMPT


class OutputGuardrailNode(AgentNode):
    name: ClassVar[str] = "output_guardrail"
    _text_generator: Final[TextGenerator]
    _logger: Logger

    def __init__(
        self,
        *,
        text_generator: TextGenerator,
        logger_factory: LoggerFactory,
    ) -> None:
        self._text_generator = text_generator
        self._logger = logger_factory(__name__)

    async def _guard_output(
        self,
        output: str,
        pii_map: dict,
        restore_pii: bool = False,
    ) -> GuardrailResult:
        self._logger.debug(
            "Verifying output compliance",
            details={"output_len": len(output)},
        )

        for pii_type, pattern in PII:
            output = re.sub(pattern, f"[{pii_type} OMITIDO]", output)

        output = deanonymize_output(output, pii_map, restore=restore_pii)
        result = await self._text_generator.generate(
            COMPLIANCE_PROMPT.format(resposta=output)
        )
        result = result.strip()

        if "RESPOSTA:" in result:
            output = result.split("RESPOSTA:", 1)[1].strip() or output

        self._logger.debug(
            "Output approved",
            details={"output_length": len(output)},
        )
        return GuardrailResult.output_aproved(output)

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        self._logger.info(
            "Agent called",
            details={
                "name": self.name,
                "input_length": len(state["messages"][-1].text),
            },
        )
        writes = agenda_evidence().writes
        if writes:
            # Trusted templates contain only server-issued IDs and status, not model
            # text or event contents. A second model cannot rewrite write evidence.
            result = GuardrailResult.output_aproved(
                "\n\n".join(creation_message(item) for item in writes)
            )
        else:
            result = await self._guard_output(
                state["messages"][-1].text,
                state["pii_map"],
            )
        self._logger.info(
            "Agent response",
            details={
                "from": self.name,
                "output_length": len(result.message),
            },
        )
        return {
            GraphStateKeys.MESSAGES: [AIMessage(content=result.message)],
            GraphStateKeys.CALLED_AGENTS: [self.name],
        }
