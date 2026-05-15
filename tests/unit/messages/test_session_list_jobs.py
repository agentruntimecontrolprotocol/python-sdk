"""§6.6 — `session.list_jobs` payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.session import ListJobsFilter, SessionListJobsPayload


def test_default_empty() -> None:
    p = SessionListJobsPayload()
    assert p.filter is None
    assert p.limit is None
    assert p.cursor is None


def test_filter_status_set() -> None:
    f = ListJobsFilter(status=("pending", "running"))
    p = SessionListJobsPayload(filter=f, limit=10)
    assert p.filter is not None
    assert "pending" in p.filter.status  # type: ignore[operator]


@pytest.mark.parametrize("limit", [0, -1, 1001])
def test_limit_bounds(limit: int) -> None:
    with pytest.raises(ValidationError):
        SessionListJobsPayload(limit=limit)
