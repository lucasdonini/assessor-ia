from typing import Any, ClassVar

from langgraph.graph.state import CompiledStateGraph

from app.application.ports.logger import Logger, LoggerFactory
from app.infrastructure.agents._core.state import GraphState, GraphStateKeys

from .._core.contracts.agent_factory import AgentFactory
from .._core.contracts.agent_node import AgentNode
from ..tools.faq_rag import FaqRag
from .faq_prompt import build_faq_prompt


class FAQAgentNode(AgentNode):
    _agent: CompiledStateGraph
    _logger: Logger
    name: ClassVar[str] = "faq"

    def __init__(
        self,
        *,
        logger_factory: LoggerFactory,
        faq_rag: FaqRag,
        agent_factory: AgentFactory,
    ) -> None:
        self._logger = logger_factory(__name__)
        prompt = build_faq_prompt(node_name=self.name, faq_rag_name=faq_rag.name)
        self._agent = agent_factory(system_prompt=prompt, tools=(faq_rag,))

    async def __call__(self, state: GraphState) -> dict[GraphStateKeys, Any]:
        input_length = len(state["messages"][-1].content)
        self._logger.info(
            "Agent called",
            details={"name": self.name, "input_length": input_length},
        )
        response = await self._agent.ainvoke(state)  # type: ignore[arg-type]
        last = (response.get("messages") or [None])[-1]
        output_length = len(last.content) if last and last.content else 0
        self._logger.info(
            "Agent response",
            details={"from": self.name, "output_length": output_length},
        )
        return {
            GraphStateKeys.MESSAGES: response.get("messages") or [],
            GraphStateKeys.CALLED_AGENTS: [self.name],
        }
