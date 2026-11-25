"""
StateFlow Logging Configuration

Structured logging with correlation IDs, execution IDs, and JSON output.
"""
import logging
import sys
from typing import Any, Dict, Optional
from uuid import uuid4

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings


def add_correlation_id(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add correlation ID to log entries."""
    correlation_id = getattr(logging, "correlation_id", None)
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def add_execution_id(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add execution ID to log entries."""
    execution_id = getattr(logging, "execution_id", None)
    if execution_id:
        event_dict["execution_id"] = execution_id
    return event_dict


def add_severity_level(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add severity level to log entries."""
    event_dict["severity"] = method_name.upper()
    return event_dict


def add_timestamp(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add ISO format timestamp to log entries."""
    from datetime import datetime, timezone
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def filter_sensitive_data(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Filter out sensitive data from log entries."""
    sensitive_keys = {
        "password", "secret", "token", "authorization", "api_key",
        "access_token", "refresh_token", "jwt", "credential"
    }

    def _filter_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        filtered = {}
        for key, value in d.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                filtered[key] = "***REDACTED***"
            elif isinstance(value, dict):
                filtered[key] = _filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [_filter_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                filtered[key] = value
        return filtered

    return _filter_dict(event_dict)


def setup_logging() -> None:
    """Configure structured logging for the application."""
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL),
    )

    # Configure structlog
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_timestamp,
        add_severity_level,
        add_correlation_id,
        add_execution_id,
        filter_sensitive_data,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.ENVIRONMENT == "development":
        # Pretty console output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set specific log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("kombu").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class LoggingContext:
    """Context manager for adding correlation/execution IDs to logs."""

    def __init__(self, correlation_id: Optional[str] = None, execution_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid4())
        self.execution_id = execution_id
        self._old_correlation_id = None
        self._old_execution_id = None

    def __enter__(self) -> "LoggingContext":
        self._old_correlation_id = getattr(logging, "correlation_id", None)
        self._old_execution_id = getattr(logging, "execution_id", None)
        logging.correlation_id = self.correlation_id
        if self.execution_id:
            logging.execution_id = self.execution_id
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._old_correlation_id is not None:
            logging.correlation_id = self._old_correlation_id
        else:
            delattr(logging, "correlation_id")

        if self._old_execution_id is not None:
            logging.execution_id = self._old_execution_id
        elif hasattr(logging, "execution_id"):
            delattr(logging, "execution_id")


# Initialize logging on module import
setup_logging()