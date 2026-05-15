"""§6.4 — heartbeat ping/pong shapes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.session import SessionPingPayload, SessionPongPayload


def test_ping_shape() -> None:
    p = SessionPingPayload(nonce="n1", sent_at="2026-05-14T12:00:00Z")
    assert p.nonce == "n1"


def test_pong_shape() -> None:
    p = SessionPongPayload(ping_nonce="n1", received_at="2026-05-14T12:00:00Z")
    assert p.ping_nonce == "n1"


def test_ping_requires_fields() -> None:
    with pytest.raises(ValidationError):
        SessionPingPayload(nonce="n1")  # type: ignore[call-arg]
