"""Structured logging for the API and the worker.

All records, from structlog loggers and from standard-library loggers (uvicorn,
SQLAlchemy, Temporal, aiokafka), go through one handler on the root logger:
- JSON lines (one object per record) outside development;
- readable, coloured console lines in development.

Values bound with structlog.contextvars.bind_contextvars (for example the request id)
are added to every record of the current request or task.
"""

import logging
import sys

import structlog

UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

# Processors that run for structlog records and for standard-library records.
_SHARED_PROCESSORS: list[structlog.typing.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
]


def setup_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """Configure logging for the whole process. Safe to call more than once.

    `level` is a standard level name (case-insensitive). Records below it are dropped.
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *_SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer: list[structlog.typing.Processor] = (
        [structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
        if json_logs
        else [structlog.dev.ConsoleRenderer()]
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=_SHARED_PROCESSORS,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                *renderer,
            ],
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # Uvicorn installs its own handlers; route its records through the shared handler.
    for name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger. Pass `__name__` so that records name their module."""
    return structlog.stdlib.get_logger(name)
