"""Tests for the canonical error taxonomy (RFC §18)."""

from __future__ import annotations

import pytest

from arcp.errors import ARCPError, ErrorCode, is_retryable_default


@pytest.mark.parametrize(
    "code",
    list(ErrorCode),
)
def test_every_error_code_is_string(code: ErrorCode) -> None:
    assert isinstance(str(code), str)
    assert str(code) == code.value


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (ErrorCode.RESOURCE_EXHAUSTED, True),
        (ErrorCode.UNAVAILABLE, True),
        (ErrorCode.DEADLINE_EXCEEDED, True),
        (ErrorCode.INTERNAL, True),
        (ErrorCode.ABORTED, True),
        (ErrorCode.INVALID_ARGUMENT, False),
        (ErrorCode.NOT_FOUND, False),
        (ErrorCode.ALREADY_EXISTS, False),
        (ErrorCode.PERMISSION_DENIED, False),
        (ErrorCode.FAILED_PRECONDITION, False),
        (ErrorCode.UNIMPLEMENTED, False),
        (ErrorCode.UNAUTHENTICATED, False),
        (ErrorCode.DATA_LOSS, False),
        (ErrorCode.OK, False),
        (ErrorCode.HEARTBEAT_LOST, False),
        (ErrorCode.LEASE_EXPIRED, False),
        (ErrorCode.LEASE_REVOKED, False),
        (ErrorCode.BACKPRESSURE_OVERFLOW, False),
        (ErrorCode.OUT_OF_RANGE, False),
        (ErrorCode.CANCELLED, False),
        (ErrorCode.UNKNOWN, False),
    ],
)
def test_retryable_defaults(code: ErrorCode, expected: bool) -> None:
    assert is_retryable_default(code) is expected


def test_error_to_payload_roundtrips_basic_fields() -> None:
    err = ARCPError(
        ErrorCode.RESOURCE_EXHAUSTED,
        "throttled",
        details={"retry_after_seconds": 30},
    )
    payload = err.to_payload()
    assert payload["code"] == "RESOURCE_EXHAUSTED"
    assert payload["message"] == "throttled"
    assert payload["retryable"] is True
    assert payload["details"] == {"retry_after_seconds": 30}
    assert "cause" not in payload


def test_error_chaining_serializes_cause() -> None:
    cause = ARCPError(ErrorCode.UNAVAILABLE, "upstream gone")
    err = ARCPError(
        ErrorCode.INTERNAL,
        "wrapping",
        cause=cause,
        trace_id="trace_x",
    )
    payload = err.to_payload()
    assert payload["cause"]["code"] == "UNAVAILABLE"
    assert payload["trace_id"] == "trace_x"


def test_error_explicit_retryable_overrides_default() -> None:
    err = ARCPError(ErrorCode.INTERNAL, "x", retryable=False)
    assert err.retryable is False
    assert err.to_payload()["retryable"] is False
