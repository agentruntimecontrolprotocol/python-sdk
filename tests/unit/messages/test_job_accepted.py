"""§7.1 — `job.accepted` payload."""

from __future__ import annotations

from arcp._messages.execution import JobAcceptedPayload


def test_accepted_shape() -> None:
    p = JobAcceptedPayload(
        job_id="job_x",
        agent="a@1",
        accepted_at="2026-05-14T12:00:00Z",
        lease={"fs.read": ["/tmp/*"]},
        budget={"USD": "USD:5.00"},
    )
    assert p.budget == {"USD": "USD:5.00"}
    assert p.lease == {"fs.read": ["/tmp/*"]}
