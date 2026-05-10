"""Canonical ARCP error taxonomy (RFC §18).

`ErrorCode` enumerates every code defined by the canonical taxonomy. Implementations
MUST use these codes when applicable; deployment-specific codes MUST be namespaced
(``arcpx.<vendor>.<NAME>``) and represented as plain strings rather than members of
this enum.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Canonical ARCP error codes (RFC §18.2)."""

    OK = "OK"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    FAILED_PRECONDITION = "FAILED_PRECONDITION"
    ABORTED = "ABORTED"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    UNIMPLEMENTED = "UNIMPLEMENTED"
    INTERNAL = "INTERNAL"
    UNAVAILABLE = "UNAVAILABLE"
    DATA_LOSS = "DATA_LOSS"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    HEARTBEAT_LOST = "HEARTBEAT_LOST"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    LEASE_REVOKED = "LEASE_REVOKED"
    BACKPRESSURE_OVERFLOW = "BACKPRESSURE_OVERFLOW"


# RFC §18.3: codes that retry by default unless the runtime declares otherwise.
_RETRYABLE_DEFAULTS: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.RESOURCE_EXHAUSTED,
        ErrorCode.UNAVAILABLE,
        ErrorCode.DEADLINE_EXCEEDED,
        ErrorCode.INTERNAL,
        ErrorCode.ABORTED,
    }
)


def is_retryable_default(code: ErrorCode) -> bool:
    """Return the default retryability classification for ``code`` per RFC §18.3."""
    return code in _RETRYABLE_DEFAULTS


class ARCPError(Exception):
    """Structured exception type matching the §18.1 error envelope.

    Boundary code (transports, dispatch handlers) catches narrow exception types
    and rethrows as ``ARCPError`` so that error envelopes can be emitted with
    canonical ``code`` values.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
        cause: ARCPError | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable if retryable is not None else is_retryable_default(code)
        self.details: dict[str, Any] = details or {}
        self.cause: ARCPError | None = cause
        self.trace_id = trace_id

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the §18.1 error payload shape."""
        payload: dict[str, Any] = {
            "code": str(self.code),
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            payload["details"] = self.details
        if self.cause is not None:
            payload["cause"] = self.cause.to_payload()
        if self.trace_id is not None:
            payload["trace_id"] = self.trace_id
        return payload
