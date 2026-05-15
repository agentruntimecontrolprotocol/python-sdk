"""§6.5 — `session.ack` payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.session import SessionAckPayload


def test_ack_zero_accepted() -> None:
    SessionAckPayload(last_processed_seq=0)


def test_ack_positive_accepted() -> None:
    SessionAckPayload(last_processed_seq=42)


def test_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        SessionAckPayload(last_processed_seq=-1)
