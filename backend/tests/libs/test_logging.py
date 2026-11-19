"""Tests for the shared structured logging configuration."""

import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
import structlog

from src.libs.core.logger import get_logger, setup_logging


def json_lines(output: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


@pytest.fixture(autouse=True)
def clean_context() -> Iterator[None]:
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


class TestJsonLogging:
    """In JSON mode every record is one JSON object per line."""

    def test_structlog_and_stdlib_records_share_one_format(self, capsys):
        """
        GIVEN JSON logging at level INFO
        WHEN a structlog logger and a stdlib logger each write a record
        THEN both lines are JSON with event, level, logger and timestamp
        AND positional arguments and extra fields are rendered
        """
        setup_logging("INFO", json_logs=True)

        get_logger("tests.app").info("hello %s", "world", user="ada")
        logging.getLogger("tests.stdlib").warning("plain %d", 3)

        app_line, stdlib_line = json_lines(capsys.readouterr().out)
        assert app_line["event"] == "hello world"
        assert app_line["level"] == "info"
        assert app_line["logger"] == "tests.app"
        assert app_line["user"] == "ada"
        assert "timestamp" in app_line
        assert stdlib_line["event"] == "plain 3"
        assert stdlib_line["level"] == "warning"
        assert stdlib_line["logger"] == "tests.stdlib"

    def test_level_filters_records(self, capsys):
        """
        GIVEN JSON logging at level WARNING
        WHEN an INFO and a WARNING record are written
        THEN only the WARNING record is written
        """
        setup_logging("warning", json_logs=True)

        logger = get_logger("tests.level")
        logger.info("hidden")
        logger.warning("shown")

        assert [line["event"] for line in json_lines(capsys.readouterr().out)] == [
            "shown"
        ]

    def test_exception_includes_traceback(self, capsys):
        """
        GIVEN JSON logging
        WHEN an exception is logged inside an except block
        THEN the line contains the traceback with the exception type
        """
        setup_logging("INFO", json_logs=True)

        try:
            raise ValueError("boom")
        except ValueError:
            get_logger("tests.exc").exception("failed")

        (line,) = json_lines(capsys.readouterr().out)
        assert line["level"] == "error"
        assert "ValueError: boom" in line["exception"]

    def test_context_variables_are_added(self, capsys):
        """
        GIVEN a request id bound to the logging context
        WHEN a record is written
        THEN the line contains the request id
        """
        setup_logging("INFO", json_logs=True)
        structlog.contextvars.bind_contextvars(request_id="req-1")

        get_logger("tests.ctx").info("inside request")

        assert json_lines(capsys.readouterr().out)[0]["request_id"] == "req-1"


class TestConsoleLogging:
    """In console mode records are readable text, not JSON."""

    def test_console_output_is_not_json(self, capsys):
        """
        GIVEN console logging
        WHEN a record is written
        THEN the line contains the event text and is not JSON
        """
        setup_logging("INFO", json_logs=False)

        get_logger("tests.console").info("readable line")

        output = capsys.readouterr().out
        assert "readable line" in output
        with pytest.raises(json.JSONDecodeError):
            json.loads(output.splitlines()[0])


class TestThirdPartyLoggers:
    """Uvicorn loggers use the shared handler instead of their own."""

    def test_uvicorn_loggers_propagate_to_root(self):
        """
        GIVEN uvicorn configured its loggers with their own handlers
        WHEN logging is set up
        THEN the uvicorn loggers have no own handlers and propagate to the root
        """
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            uvicorn_logger = logging.getLogger(name)
            uvicorn_logger.addHandler(logging.NullHandler())
            uvicorn_logger.propagate = False

        setup_logging("INFO", json_logs=True)

        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            assert logging.getLogger(name).handlers == []
            assert logging.getLogger(name).propagate is True

    def test_setup_is_idempotent(self):
        """
        GIVEN logging is set up twice
        WHEN the root handlers are counted
        THEN there is exactly one handler (no duplicate lines)
        """
        setup_logging("INFO", json_logs=True)
        setup_logging("INFO", json_logs=True)

        assert len(logging.getLogger().handlers) == 1
