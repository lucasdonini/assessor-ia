import re
from typing import Any, ClassVar, Final

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph import END

from app.application.ports.logger import Logger, LoggerFactory
from app.application.ports.text_generator import TextGenerator
from app.infrastructure.agents._core.state import GraphState, GraphStateKeys
from app.infrastructure.agents.guardrails.result import GuardrailResult

from .._core.contracts.agent_node import AgentNode
from .anonymization import anonymize_input
from .guardrails_config import BLOCK_RESPONSES, INJECTION_PATTERNS, INTERN_DATA_KEYWORDS
from .guardrails_prompts import CLASSIFIER_PROMPT


class InputGuardrailNode(AgentNode):
    name: ClassVar[str] = "input_guardrail"
    _text_generator: Final[TextGenerator]
    _logger: Logger
    _approved_route: str

    def __init__(
        self,
        *,
        approved_route: str,
        text_generator: TextGenerator,
        logger_factory: LoggerFactory,
    ) -> None:
        self._text_generator = text_generator
        self._approved_route = approved_route
        self._logger = logger_factory(__name__)

    def _check_prompt_injection(self, input: str) -> bool:
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, input, re.IGNORECASE):
                self._logger.debug(
                    "Input blocked for prompt injection",
                    details={
                        "reason": "prompt_injection",
                        "input_length": len(input),
                    },
                )
                return False
        return True

    def _check_pii_access(self, input: str) -> bool:
        text_lower = input.lower()
        for keyword in INTERN_DATA_KEYWORDS:
            if keyword in text_lower:
                self._logger.debug(
                    "Input blocked for PII",
                    details={"reason": "acesso_dados_internos"},
                )
                return False
        return True

    async def _classify_with_llm(self, input: str) -> GuardrailResult:
        prompt = CLASSIFIER_PROMPT.format(mensagem=input)
        response = await self._text_generator.generate(prompt)

        category: str | None = None
        for line in response.splitlines():
            if line.strip().upper().startswith("CATEGORIA:"):
                category = line.split(":", 1)[1].strip().upper()
                break

        if category == "APROVADO":
            self._logger.debug(
                "Input approved",
                details={"input_length": len(input), "category": category},
            )
            return GuardrailResult.input_aproved(input)

        if category in BLOCK_RESPONSES:
            reason, message = BLOCK_RESPONSES[category]
            return GuardrailResult.block(reason, message)

        self._logger.warning(
            "Input blocked due to undetermined classification",
            details={"category": category},
        )
        return GuardrailResult.block(
            "classificacao_indeterminada",
            "Não consigo processar essa solicitação no momento. Tente reformulá-la.",
        )

    async def _guard_input(self, input: str) -> GuardrailResult:
        """Run input checks in ascendent cost order:
        Deterministic first, then LLM only if needed.
        """

        self._logger.debug(
            "Verifying input compliance",
            details={"input_len": len(input)},
        )

        if not self._check_prompt_injection(input):
            return GuardrailResult.block(
                "prompt_injection", "Não consigo processar essa solicitação."
            )

        if not self._check_pii_access(input):
            return GuardrailResult.block(
                "acesso_dados_internos",
                "Não tenho como compartilhar informações internas do sistema.",
            )

        try:
            return await self._classify_with_llm(input)
        except Exception as exc:
            self._logger.exception(
                "Input classifier failed",
                exception=exc,
                details={"stage": "classification"},
            )
            return GuardrailResult.block(
                "classificador_indisponivel",
                (
                    "Não consigo processar essa solicitação no momento. "
                    "Tente novamente mais tarde."
                ),
            )

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        user_input = state["messages"][-1]
        assert user_input.id is not None

        anonymized, pii_map = anonymize_input(user_input.text)
        self._logger.info(
            "Agent called",
            details={
                "name": self.name,
                "input_length": len(anonymized),
            },
        )
        result = await self._guard_input(anonymized)

        if result.blocked:
            self._logger.info(
                "Agent response",
                details={
                    "from": self.name,
                    "status": "blocked",
                    "reason": result.blocked,
                },
            )
            return {
                GraphStateKeys.ROUTE: END,
                GraphStateKeys.GUARDRAIL_REASON: result.reason,
                GraphStateKeys.CALLED_AGENTS: [self.name],
                GraphStateKeys.MESSAGES: [AIMessage(content=result.message)],
            }

        self._logger.info(
            "Agent response",
            details={"from": self.name, "status": "approved"},
        )
        return {
            GraphStateKeys.ROUTE: self._approved_route,
            GraphStateKeys.GUARDRAIL_REASON: None,
            GraphStateKeys.CALLED_AGENTS: [self.name],
            GraphStateKeys.PII_MAP: pii_map,
            GraphStateKeys.MESSAGES: [
                RemoveMessage(id=user_input.id),
                HumanMessage(content=result.message),
            ],
        }
