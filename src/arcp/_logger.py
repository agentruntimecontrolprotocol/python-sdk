"""structlog-based logger factory; emits through stdlib logging by default."""

from __future__ import annotations

import logging
from copy import deepcopy
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


def redact_credentials(obj: Any) -> Any:
    """Return a copy with every `credentials[*].value` replaced by `<redacted>`."""
    out = deepcopy(obj)
    _redact_credentials_in_place(out)
    return out


def _redact_credentials_in_place(obj: Any) -> None:
    if isinstance(obj, dict):
        mapping: dict[Any, Any] = obj
        credentials = mapping.get("credentials")
        if isinstance(credentials, (list, tuple)):
            for cred in credentials:
                if isinstance(cred, dict) and "value" in cred:
                    cred["value"] = "<redacted>"
        for value in mapping.values():
            _redact_credentials_in_place(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _redact_credentials_in_place(item)


__all__ = ("get_logger", "redact_credentials")
