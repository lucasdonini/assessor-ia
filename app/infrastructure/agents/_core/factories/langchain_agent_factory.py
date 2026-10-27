from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain.chat_models import BaseChatModel
from langchain.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel


class LangChainAgentFactory:
    def __init__(
        self,
        *,
        llm: BaseChatModel,
        middlewares: Sequence[AgentMiddleware] = (),
    ) -> None:
        self._llm = llm
        self._middlewares = tuple(middlewares)

    def __call__(
        self,
        *,
        system_prompt: str,
        tools: Sequence[BaseTool] = (),
        response_format: type[BaseModel] | None = None,
    ) -> CompiledStateGraph:
        return create_agent(
            model=self._llm,
            system_prompt=system_prompt,
            # Keep one tool-compatible strategy across primary/fallback models.
            # Groq rejects native JSON mode combined with function calling.
            response_format=(
                ToolStrategy(response_format)
                if response_format is not None and tools
                else response_format
            ),
            tools=list(tools),
            middleware=list(self._middlewares),
        )
