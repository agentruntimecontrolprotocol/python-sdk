"""§7.6 — `job.subscribed` response shape."""

from __future__ import annotations

from arcp._messages.execution import JobSubscribedPayload


def test_subscribed_shape() -> None:
    p = JobSubscribedPayload(
        request_id="env-x",
        job_id="job_x",
        current_status="running",
        agent="a@1",
    )
    assert p.subscribed_from == 0
    assert p.replayed == 0
    assert p.lease == {}
