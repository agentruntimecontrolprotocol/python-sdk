"""§5.1 — `trace_id` is 32 lowercase hex chars, non-zero, OPTIONAL."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp import Envelope
from arcp._ulid import new_ulid


def test_valid_trace_id_accepted() -> None:
    trace = "0af7651916cd43dd8448eb211c80319c"
    env = Envelope(id=new_ulid(), type="session.ping", trace_id=trace, payload={})
    assert env.trace_id == trace


def test_trace_id_optional() -> None:
    env = Envelope(id=new_ulid(), type="session.ping", payload={})
    assert env.trace_id is None


def test_zero_trace_id_rejected() -> None:
    with pytest.raises(ValidationError):
        Envelope(id=new_ulid(), type="session.ping", trace_id="0" * 32, payload={})


@pytest.mark.parametrize(
    "bad",
    [
        "ABCDEF",  # uppercase, too short
        "0AF7651916CD43DD8448EB211C80319C",  # uppercase
        "not-hex-not-hex-not-hex-not-hex-x",
        "0af7651916cd43dd8448eb211c80319",  # 31 chars
    ],
)
def test_bad_trace_id_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        Envelope(id=new_ulid(), type="session.ping", trace_id=bad, payload={})
