"""§5.1 — `id` MUST be a ULID, UUIDv7, or prefixed ULID like `job_...`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp import Envelope
from arcp._ulid import new_envelope_id, new_job_id, new_session_id


def test_ulid_accepted() -> None:
    env = Envelope(id=new_envelope_id(), type="session.ping", payload={})
    assert len(env.id) == 26


def test_prefixed_ulid_accepted() -> None:
    Envelope(id=new_job_id(), type="job.event", payload={})
    Envelope(id=new_session_id(), type="session.ping", payload={})


def test_uuidv7_accepted() -> None:
    # A valid UUIDv7 example.
    uuid7 = "017f22e2-79b0-7cc3-98c4-dc0c0c07398f"
    env = Envelope(id=uuid7, type="session.ping", payload={})
    assert env.id == uuid7


@pytest.mark.parametrize(
    "bad",
    [
        "not-a-ulid",
        "01HXXXXXX",  # too short
        "01HXXXXX0123456789ABCDE!@#",  # invalid chars
        "",
    ],
)
def test_bad_id_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        Envelope(id=bad, type="session.ping", payload={})
