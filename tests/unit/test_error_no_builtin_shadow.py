"""#75 — ARCP error classes must not shadow builtin Timeout/Cancelled errors."""

from __future__ import annotations

import builtins

import arcp
from arcp._errors import (
    ARCPCancelledError,
    ARCPTimeoutError,
    error_class_for,
    error_from_payload,
)


def test_arcp_no_longer_exports_shadowing_names() -> None:
    # `from arcp import TimeoutError` / `CancelledError` must not resolve to
    # ARCP-defined classes that silently replace the builtins.
    assert not hasattr(arcp, "TimeoutError")
    assert not hasattr(arcp, "CancelledError")


def test_renamed_classes_keep_their_codes() -> None:
    assert ARCPTimeoutError.code == "TIMEOUT"
    assert ARCPCancelledError.code == "CANCELLED"
    assert not issubclass(ARCPTimeoutError, builtins.TimeoutError)


def test_error_code_mapping_round_trips() -> None:
    assert error_class_for("TIMEOUT") is ARCPTimeoutError
    assert error_class_for("CANCELLED") is ARCPCancelledError
    err = error_from_payload({"code": "TIMEOUT", "message": "boom", "retryable": False})
    assert isinstance(err, ARCPTimeoutError)
    assert err.code == "TIMEOUT"


def test_public_api_exposes_prefixed_names() -> None:
    assert arcp.ARCPTimeoutError is ARCPTimeoutError
    assert arcp.ARCPCancelledError is ARCPCancelledError
