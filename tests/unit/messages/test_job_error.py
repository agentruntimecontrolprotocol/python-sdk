"""§7.3 / §12 — `job.error` payload."""

from __future__ import annotations

from arcp import ERROR_CODES
from arcp._messages.execution import JobErrorPayload


def test_job_error_shape() -> None:
    p = JobErrorPayload(
        code="LEASE_EXPIRED",
        message="lease expired",
        retryable=False,
        completed_at="2026-05-14T12:00:00Z",
    )
    assert p.final_status == "error"


def test_canonical_codes_present() -> None:
    # Spot-check canonical codes per §12.
    expected = {
        "PERMISSION_DENIED",
        "LEASE_SUBSET_VIOLATION",
        "JOB_NOT_FOUND",
        "DUPLICATE_KEY",
        "AGENT_NOT_AVAILABLE",
        "AGENT_VERSION_NOT_AVAILABLE",
        "CANCELLED",
        "TIMEOUT",
        "RESUME_WINDOW_EXPIRED",
        "HEARTBEAT_LOST",
        "LEASE_EXPIRED",
        "BUDGET_EXHAUSTED",
        "INVALID_REQUEST",
        "UNAUTHENTICATED",
        "INTERNAL_ERROR",
    }
    assert expected <= set(ERROR_CODES)
