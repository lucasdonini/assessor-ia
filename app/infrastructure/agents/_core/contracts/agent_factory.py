from typing import Protocol, Sequence

from langchain.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel


class AgentFactory(Protocol):
    def __call__(
        self,
        *,
        system_prompt: str,
        tools: Sequence[BaseTool] = (),
        response_format: type[BaseModel] | None = None,
    ) -> CompiledStateGraph: ...
