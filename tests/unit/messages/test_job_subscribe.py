"""§7.6 — `job.subscribe` payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.execution import JobSubscribePayload


def test_minimum() -> None:
    p = JobSubscribePayload(job_id="job_x")
    assert p.history is False
    assert p.from_event_seq is None


def test_history_with_from_seq() -> None:
    p = JobSubscribePayload(job_id="job_x", history=True, from_event_seq=10)
    assert p.from_event_seq == 10


def test_negative_from_seq_rejected() -> None:
    with pytest.raises(ValidationError):
        JobSubscribePayload(job_id="job_x", from_event_seq=-1)
