"""§7.4 — `job.cancel` payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.execution import JobCancelPayload


def test_cancel_minimum() -> None:
    p = JobCancelPayload(reason="user_requested")
    assert p.code is None


def test_reason_required() -> None:
    with pytest.raises(ValidationError):
        JobCancelPayload()  # type: ignore[call-arg]
