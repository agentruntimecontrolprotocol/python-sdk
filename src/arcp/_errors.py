"""ARCP error hierarchy: 15 typed exceptions corresponding to spec §12 codes."""

from __future__ import annotations

from typing import Any, ClassVar


class ARCPError(Exception):
    """Base class for ARCP-defined errors. Subclasses fix `code` and `default_retryable`."""

    code: ClassVar[str] = "INTERNAL_ERROR"
    default_retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = self.default_retryable if retryable is None else retryable
        self.details: dict[str, Any] = details or {}

    def to_payload(self) -> dict[str, Any]:
        """Return the wire-shape error body."""
        out: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            out["details"] = self.details
        return out


class PermissionDeniedError(ARCPError):
    code = "PERMISSION_DENIED"
    default_retryable = False


class LeaseSubsetViolationError(ARCPError):
    code = "LEASE_SUBSET_VIOLATION"
    default_retryable = False


class JobNotFoundError(ARCPError):
    code = "JOB_NOT_FOUND"
    default_retryable = False


class DuplicateKeyError(ARCPError):
    code = "DUPLICATE_KEY"
    default_retryable = False


class AgentNotAvailableError(ARCPError):
    code = "AGENT_NOT_AVAILABLE"
    default_retryable = False


class AgentVersionNotAvailableError(ARCPError):
    code = "AGENT_VERSION_NOT_AVAILABLE"
    default_retryable = False


class CancelledError(ARCPError):
    code = "CANCELLED"
    default_retryable = False


class TimeoutError(ARCPError):
    code = "TIMEOUT"
    default_retryable = False


class ResumeWindowExpiredError(ARCPError):
    code = "RESUME_WINDOW_EXPIRED"
    default_retryable = False


class HeartbeatLostError(ARCPError):
    code = "HEARTBEAT_LOST"
    default_retryable = False


class LeaseExpiredError(ARCPError):
    code = "LEASE_EXPIRED"
    default_retryable = False


class BudgetExhaustedError(ARCPError):
    code = "BUDGET_EXHAUSTED"
    default_retryable = False


class InvalidRequestError(ARCPError):
    code = "INVALID_REQUEST"
    default_retryable = False


class UnauthenticatedError(ARCPError):
    code = "UNAUTHENTICATED"
    default_retryable = False


class InternalError(ARCPError):
    code = "INTERNAL_ERROR"
    default_retryable = True


_BY_CODE: dict[str, type[ARCPError]] = {
    cls.code: cls
    for cls in (
        PermissionDeniedError,
        LeaseSubsetViolationError,
        JobNotFoundError,
        DuplicateKeyError,
        AgentNotAvailableError,
        AgentVersionNotAvailableError,
        CancelledError,
        TimeoutError,
        ResumeWindowExpiredError,
        HeartbeatLostError,
        LeaseExpiredError,
        BudgetExhaustedError,
        InvalidRequestError,
        UnauthenticatedError,
        InternalError,
    )
}


ERROR_CODES: tuple[str, ...] = tuple(_BY_CODE.keys())


def error_class_for(code: str) -> type[ARCPError]:
    """Return the typed class for `code`; unknown codes collapse to `InternalError`."""
    return _BY_CODE.get(code, InternalError)


def error_from_payload(payload: dict[str, Any]) -> ARCPError:
    """Construct the typed exception from a wire `error` payload."""
    code = str(payload.get("code", "INTERNAL_ERROR"))
    cls = error_class_for(code)
    msg = str(payload.get("message", code))
    retryable = payload.get("retryable")
    if not isinstance(retryable, bool):
        retryable = None
    details = payload.get("details") if isinstance(payload.get("details"), dict) else None
    return cls(msg, retryable=retryable, details=details)


__all__ = (
    "ERROR_CODES",
    "ARCPError",
    "AgentNotAvailableError",
    "AgentVersionNotAvailableError",
    "BudgetExhaustedError",
    "CancelledError",
    "DuplicateKeyError",
    "HeartbeatLostError",
    "InternalError",
    "InvalidRequestError",
    "JobNotFoundError",
    "LeaseExpiredError",
    "LeaseSubsetViolationError",
    "PermissionDeniedError",
    "ResumeWindowExpiredError",
    "TimeoutError",
    "UnauthenticatedError",
    "error_class_for",
    "error_from_payload",
)
