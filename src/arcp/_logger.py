"""structlog-based logger factory; emits through stdlib logging by default."""

from __future__ import annotations

import logging
from typing import Any

import structlog

_configured = False


def _configure_once() -> None:
    global _configured
    if _configured:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None, **initial: Any) -> Any:
    """Return a structlog bound logger; idempotent on first call."""
    _configure_once()
    log = structlog.get_logger(name) if name is not None else structlog.get_logger()
    if initial:
        log = log.bind(**initial)
    return log


__all__ = ("get_logger",)
