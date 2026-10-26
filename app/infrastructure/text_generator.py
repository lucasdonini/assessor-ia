from contextlib import nullcontext

from langchain.chat_models import BaseChatModel
from langsmith import tracing_context

from app.infrastructure.observability import has_active_turn


class LLMTextGenerator:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def generate(self, prompt: str) -> str:
        # Only graph turns may export through the injected private tracer.
        with nullcontext() if has_active_turn() else tracing_context(enabled=False):
            result = await self._llm.ainvoke(prompt)
        if not isinstance(result.content, str):
            raise TypeError(
                "Text generator returned non-text content: "
                f"{type(result.content).__name__!r}"
            )
        return result.content
