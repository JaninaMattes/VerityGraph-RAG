# src/utils/logger.py
# custom structlog setup

import logging
from typing import Any

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """Configures centralized structured logging for the entire ASGI application."""

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,  # Thread-safe context sharing
        structlog.processors.add_log_level,  # Adds "level": "info"
        structlog.processors.TimeStamper(fmt="iso"),  # ISO timestamps
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,  # Extracts and formats exception info
        structlog.processors.JSONRenderer(),  # Converts log entries into JSON format
    ]

    # Configure structlogger
    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    # Configure the root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Returns a named structured logger instance for a package module."""
    return structlog.get_logger(name)
