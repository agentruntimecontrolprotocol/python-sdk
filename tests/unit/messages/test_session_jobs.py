"""§6.6 — `session.jobs` response shape."""

from __future__ import annotations

from arcp._messages.session import JobListEntry, SessionJobsPayload


def test_jobs_response_echoes_request_id() -> None:
    p = SessionJobsPayload(
        request_id="env-123",
        jobs=(
            JobListEntry(
                job_id="job_x",
                agent="a@1",
                status="pending",
                submitted_at="2026-05-14T12:00:00Z",
            ),
        ),
    )
    assert p.request_id == "env-123"
    assert p.jobs[0].job_id == "job_x"
    assert p.next_cursor is None
