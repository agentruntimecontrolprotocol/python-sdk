"""Validation tests for session message payloads (RFC §8)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp.messages.session import (
    AuthBlock,
    Capabilities,
    RuntimeIdentity,
    SessionAcceptedPayload,
    SessionOpenPayload,
)


def test_session_open_minimum() -> None:
    payload = SessionOpenPayload.model_validate(
        {
            "auth": {"scheme": "bearer", "token": "tk"},
            "client": {"kind": "test", "version": "0.0.1"},
            "capabilities": {},
        }
    )
    assert payload.auth.scheme == "bearer"
    assert payload.client.kind == "test"
    assert payload.capabilities.streaming is False


def test_session_open_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        SessionOpenPayload.model_validate(
            {
                "auth": {"scheme": "bearer", "token": "tk"},
                "client": {"kind": "test", "version": "0.0.1"},
                "capabilities": {},
                "extra": True,
            }
        )


def test_capabilities_extras_allowed() -> None:
    caps = Capabilities.model_validate({"streaming": True, "vendor.flag": True})
    assert caps.streaming is True
    assert caps.model_extra is not None


def test_session_accepted_roundtrip() -> None:
    accepted = SessionAcceptedPayload(
        session_id="sess_x",
        runtime=RuntimeIdentity(kind="rt", version="1"),
        capabilities=Capabilities(streaming=True),
    )
    dumped = accepted.model_dump()
    assert dumped["session_id"] == "sess_x"


def test_auth_scheme_strict() -> None:
    with pytest.raises(ValidationError):
        AuthBlock.model_validate({"scheme": "weird"})
