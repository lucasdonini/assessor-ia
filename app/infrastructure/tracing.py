from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client, tracing_context

from app.application.ports.logger import LoggerFactory

_NAMES = {
    "LangGraph",
    "input_guardrail",
    "router",
    "financial",
    "agenda",
    "faq",
    "orquestrator",
    "output_guardrail",
    "ChatGroq",
    "ChatGoogleGenerativeAI",
    "model",
    "tools",
    "agent",
    "invoke",
}
_MODELS = {"gemini-2.5-flash", "openai/gpt-oss-120b", "qwen/qwen3.6-27b"}
_PROVIDERS = {"groq", "google", "google_genai"}


def technical_metadata(value: dict[str, Any]) -> dict[str, Any]:
    """Allowlist values as well as keys: provider metadata is not trusted text."""
    result: dict[str, Any] = {}
    for key, allowed in (("ls_provider", _PROVIDERS), ("ls_model_name", _MODELS)):
        item = value.get(key)
        if isinstance(item, str) and item in allowed:
            result[key] = item
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        item = value.get(key)
        if isinstance(item, int) and not isinstance(item, bool) and item >= 0:
            result[key] = item
    usage = value.get("usage_metadata")
    if isinstance(usage, dict):
        result["usage_metadata"] = {
            key: usage[key]
            for key in ("input_tokens", "output_tokens", "total_tokens")
            if isinstance(usage.get(key), int)
            and not isinstance(usage[key], bool)
            and usage[key] >= 0
        }
    turn_id = value.get("turn_id")
    if isinstance(turn_id, str):
        from uuid import UUID

        try:
            result["turn_id"] = str(UUID(turn_id))
        except ValueError:
            pass
    return result


def private_run_ops(runs: Sequence[dict]) -> Sequence[dict]:
    """Last outbound boundary: strip content, serialized objects, events and errors."""
    allowed = {
        "id",
        "trace_id",
        "parent_run_id",
        "dotted_order",
        "start_time",
        "end_time",
        "run_type",
        "session_name",
        "session_id",
    }
    result = []
    for run in runs:
        safe = {key: value for key, value in run.items() if key in allowed}
        name = run.get("name")
        if name is not None:
            safe["name"] = (
                name if isinstance(name, str) and name in _NAMES else "operation"
            )
        if run.get("error"):
            safe["error"] = "execution_failure"
        if "inputs" in run:
            safe["inputs"] = {}
        if "outputs" in run:
            safe["outputs"] = {}
        safe["extra"] = {
            "metadata": technical_metadata(
                (run.get("extra") or {}).get("metadata") or {}
            )
        }
        result.append(safe)
    return result


class PrivateTracing:
    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str,
        project: str,
        logger_factory: LoggerFactory,
    ) -> None:
        self._logger = logger_factory(__name__)
        self._project = project
        self._client: Client | None = None
        if enabled and api_key and api_key != "cole_a_chave_aqui":
            try:
                self._client = Client(
                    api_key=api_key,
                    hide_inputs=True,
                    hide_outputs=True,
                    hide_metadata=technical_metadata,
                    anonymizer=lambda value: (
                        {"error": "execution_failure"}
                        if "error" in value
                        else technical_metadata(value)
                    ),
                    omit_traced_runtime_info=True,
                    process_buffered_run_ops=private_run_ops,
                    run_ops_buffer_size=1,
                    tracing_error_callback=lambda _: self._logger.warning(
                        "Trace export unavailable"
                    ),
                )
            except Exception:
                self._logger.warning("Trace export unavailable")

    def callbacks(self) -> list[BaseCallbackHandler]:
        if self._client is None:
            return []
        try:
            return [LangChainTracer(client=self._client, project_name=self._project)]
        except Exception:
            self._logger.warning("Trace export unavailable")
            return []

    @contextmanager
    def scope(self) -> Generator[None]:
        with tracing_context(
            enabled=self._client is not None,
            client=self._client,
            project_name=self._project,
        ):
            yield

    def close(self) -> None:
        if self._client:
            try:
                self._client.flush()
                self._client.close()
            except Exception:
                self._logger.warning("Trace export unavailable")
