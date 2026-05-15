"""§7.6 — `job.unsubscribe` payload."""

from __future__ import annotations

from arcp._messages.execution import JobUnsubscribePayload


def test_unsubscribe_shape() -> None:
    p = JobUnsubscribePayload(job_id="job_x")
    assert p.job_id == "job_x"
