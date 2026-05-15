"""§13.7 / §12 — `session.error` payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.session import SessionErrorPayload


def test_session_error_shape() -> None:
    p = SessionErrorPayload(
        code="AGENT_VERSION_NOT_AVAILABLE",
        message="not registered",
        retryable=False,
    )
    assert p.code == "AGENT_VERSION_NOT_AVAILABLE"


def test_required_fields() -> None:
    with pytest.raises(ValidationError):
        SessionErrorPayload(message="x")  # type: ignore[call-arg]
