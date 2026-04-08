"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict, Processor

from app.core.config import settings


def add_request_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add request ID to log context if available."""
    from contextvars import ContextVar

    request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
    request_id = request_id_var.get()

    if request_id:
        event_dict["request_id"] = request_id

    return event_dict


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to all logs."""
    event_dict["app"] = "rag-api"
    event_dict["environment"] = settings.environment
    return event_dict


def setup_logging() -> None:
    """Configure structured logging for the application."""

    # Define processors based on environment
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_app_context,
        add_request_id,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_development:
        # Human-readable console output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    else:
        # JSON output for production (easier to parse with log aggregators)
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    # Configure uvicorn access logs
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        Configured structlog logger.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_action", user_id=123, action="login")
    """
    return structlog.get_logger(name)


class LoggerContextManager:
    """Context manager for adding temporary log context."""

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize with context variables.

        Args:
            **kwargs: Key-value pairs to add to log context.
        """
        self.context = kwargs
        self.token: Any = None

    def __enter__(self) -> "LoggerContextManager":
        """Enter context and bind variables."""
        self.token = structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context and clear variables."""
        structlog.contextvars.clear_contextvars()


def log_context(**kwargs: Any) -> LoggerContextManager:
    """
    Create a context manager for temporary log context.

    Args:
        **kwargs: Key-value pairs to add to log context.

    Returns:
        Context manager that adds context variables.

    Example:
        >>> with log_context(user_id=123, request_id="abc"):
        ...     logger.info("processing_request")
    """
    return LoggerContextManager(**kwargs)
