"""§7.3 / §8.4 — `job.result` payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.execution import JobResultPayload


def test_success_with_inline_result() -> None:
    p = JobResultPayload(
        final_status="success",
        result={"answer": 42},
        completed_at="2026-05-14T12:00:00Z",
    )
    assert p.result == {"answer": 42}


def test_success_with_streamed_id() -> None:
    p = JobResultPayload(
        final_status="success",
        result_id="res_x",
        result_size=10,
        completed_at="2026-05-14T12:00:00Z",
    )
    assert p.result_id == "res_x"


def test_invalid_final_status() -> None:
    with pytest.raises(ValidationError):
        JobResultPayload(
            final_status="error",  # pyright: ignore[reportArgumentType]
            completed_at="2026-05-14T12:00:00Z",
        )
