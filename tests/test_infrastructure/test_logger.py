import asyncio
import io
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure import logger as logger_module


@pytest.fixture(autouse=True)
def restore_logging() -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    original_factory = logging.getLogRecordFactory()
    root.handlers.clear()
    logger_module._session_interactions.clear()

    yield

    for handler in root.handlers:
        handler.close()
    root.handlers.clear()
    root.handlers.extend(original_handlers)
    root.setLevel(original_level)
    logging.setLogRecordFactory(original_factory)
    logger_module._session_interactions.clear()


def _record(name: str = "app.agents.graph") -> logging.LogRecord:
    return logging.LogRecord(name, logging.INFO, "", 0, "Message", (), None)


def test_context_filter_reads_context_values() -> None:
    with (
        logger_module.bind_session_context("session-123"),
        logger_module.bind_trace_context("trace-456"),
    ):
        logger_module.increment_interaction()
        record = _record()

        logger_module.ContextFilter().filter(record)

    assert record.session_id == "session-123"
    assert record.trace_id == "trace-456"
    assert record.interaction == 1
    assert record.agent == "agents.graph"

    restored_record = _record()
    logger_module.ContextFilter().filter(restored_record)
    assert restored_record.session_id == ""
    assert restored_record.trace_id == ""
    assert restored_record.interaction == 0


@pytest.mark.asyncio
async def test_context_values_are_isolated_between_tasks() -> None:
    logger_module._interaction_counter.set(0)

    async def read_context(session_id: str, trace_id: str) -> tuple[str, str, int]:
        with (
            logger_module.bind_session_context(session_id),
            logger_module.bind_trace_context(trace_id),
        ):
            logger_module.increment_interaction()
            record = _record()
            logger_module.ContextFilter().filter(record)
            return record.session_id, record.trace_id, record.interaction

    first, second = await asyncio.gather(
        read_context("session-a", "trace-a"),
        read_context("session-b", "trace-b"),
    )

    assert first == ("session-a", "trace-a", 1)
    assert second == ("session-b", "trace-b", 1)


@pytest.mark.asyncio
async def test_interactions_are_sequential_for_the_same_session() -> None:
    async def read_interaction() -> int:
        with logger_module.bind_session_context("session-a"):
            return logger_module.increment_interaction()

    first, second = await asyncio.gather(read_interaction(), read_interaction())

    assert sorted((first, second)) == [1, 2]


def test_setup_logger_does_not_create_file_when_disabled(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "app.log"

    with (
        patch.object(logger_module.settings, "log_to_file", False),
        patch.object(logger_module.settings, "log_file", str(log_file)),
    ):
        logger_module.setup_logger()

    assert not log_file.parent.exists()
    assert len(logging.getLogger().handlers) == 1


def test_setup_logger_writes_structured_file_when_enabled(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "app.log"

    with (
        patch.object(logger_module.settings, "log_to_file", True),
        patch.object(logger_module.settings, "log_file", str(log_file)),
    ):
        with (
            logger_module.bind_session_context("session-123"),
            logger_module.bind_trace_context("trace-456"),
        ):
            logger_module.setup_logger()
            logging.getLogger("app.agents.graph").info(
                "Message", extra={"details": {"key": "value"}}
            )

    content = log_file.read_text(encoding="utf-8")
    assert "session=session-" in content
    assert "trace=trace-45" in content
    assert '"key": "value"' in content


def test_console_formatter_hides_details_outside_debug() -> None:
    record = _record()
    record.details = {"key": "value"}

    content = logger_module.ConsoleFormatter(debug=False).format(record)

    assert "INFO:     Message" in content
    assert "agents.graph" not in content
    assert "key" not in content


def test_console_formatter_shows_details_in_debug() -> None:
    record = _record()
    record.agent = "agents.graph"
    record.details = {"key": "value"}

    content = logger_module.ConsoleFormatter(debug=True).format(record)

    assert "INFO:     [agents.graph] Message" in content
    assert '"key": "value"' in content


def test_console_formatter_shows_agent_name_for_info_flow_events() -> None:
    record = _record()
    record.details = {"name": "faq", "input": "Question"}

    content = logger_module.ConsoleFormatter(debug=False).format(record)

    assert content == "INFO:     [faq] Message"
    assert "Question" not in content


def test_console_formatter_shows_agent_chain_for_info_flow_events() -> None:
    record = _record()
    record.details = {"chain": "router -> faq"}

    content = logger_module.ConsoleFormatter(debug=False).format(record)

    assert content == "INFO:     [router -> faq] Message"


def test_console_formatter_colors_only_level_prefix() -> None:
    formatter = logger_module.ConsoleFormatter(debug=False)
    formatter.use_colors = True

    content = formatter.format(_record())

    assert content == "\033[32mINFO\033[0m:     Message"


def test_console_formatter_preserves_traceback() -> None:
    try:
        raise RuntimeError("failure")
    except RuntimeError:
        record = logging.LogRecord(
            "app.agents.graph",
            logging.ERROR,
            "",
            0,
            "Failed",
            (),
            exc_info=sys.exc_info(),
        )

    content = logger_module.ConsoleFormatter(debug=False).format(record)

    assert "ERROR:    Failed" in content
    assert "RuntimeError: failure" in content


def test_setup_logger_uses_debug_console_format() -> None:
    output = io.StringIO()

    with (
        patch.object(logger_module.settings, "log_level", "DEBUG"),
        patch.object(logger_module.settings, "log_to_file", False),
        patch.object(logger_module.sys, "stdout", output),
    ):
        logger_module.setup_logger()
        logging.getLogger("app.agents.graph").info(
            "Message", extra={"details": {"key": "value"}}
        )

    content = output.getvalue()
    assert "INFO:     [agents.graph] Message" in content
    assert '"key": "value"' in content


def test_python_logger_adapter_translates_structured_details() -> None:
    native_logger = MagicMock(spec=logging.Logger)
    adapter = logger_module.PythonLoggerAdapter(native_logger)

    adapter.debug("Message", details={"key": "value"})

    native_logger.debug.assert_called_once_with(
        "Message",
        extra={"details": {"key": "value"}},
    )


def test_python_logger_adapter_preserves_captured_exception() -> None:
    native_logger = MagicMock(spec=logging.Logger)
    adapter = logger_module.PythonLoggerAdapter(native_logger)
    exception = RuntimeError("failure")

    adapter.exception(
        "Message",
        exception=exception,
        details={"key": "value"},
    )

    native_logger.exception.assert_called_once_with(
        "Message",
        exc_info=exception,
        extra={"details": {"key": "value"}},
    )


def test_user_context_restores_and_partitions_session_counters():
    for user in ("first", "second"):
        with (
            logger_module.bind_user_logging_context(user),
            logger_module.bind_session_context("same"),
        ):
            assert logger_module.increment_interaction() == 1
            record = _record()
            logger_module.ContextFilter().filter(record)
            assert record.user_id == user
            logger_module.clear_session_interactions("same")
    record = _record()
    logger_module.ContextFilter().filter(record)
    assert record.user_id == ""
    assert not logger_module._session_interactions
