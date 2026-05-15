"""§6.7 — `session.bye` payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.session import SessionByePayload


def test_bye_minimum() -> None:
    p = SessionByePayload(reason="done")
    assert p.code is None


def test_bye_requires_reason() -> None:
    with pytest.raises(ValidationError):
        SessionByePayload()  # type: ignore[call-arg]
