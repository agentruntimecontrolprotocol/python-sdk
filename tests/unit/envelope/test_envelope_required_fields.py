"""§5.1 — `id`, `type`, `payload` required; `event_seq` must be positive when set."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp import Envelope
from arcp._ulid import new_ulid


def test_id_required() -> None:
    with pytest.raises(ValidationError):
        Envelope(type="session.ping", payload={})  # type: ignore[call-arg]


def test_type_required() -> None:
    with pytest.raises(ValidationError):
        Envelope(id=new_ulid(), payload={})  # type: ignore[call-arg]


def test_payload_defaults_to_empty_dict() -> None:
    env = Envelope(id=new_ulid(), type="session.ping")
    assert env.payload == {}


@pytest.mark.parametrize("bad", [0, -1, -100])
def test_event_seq_must_be_positive(bad: int) -> None:
    with pytest.raises(ValidationError):
        Envelope(id=new_ulid(), type="job.event", event_seq=bad, payload={})


def test_event_seq_optional() -> None:
    env = Envelope(id=new_ulid(), type="session.ping", payload={})
    assert env.event_seq is None


def test_event_seq_positive_accepted() -> None:
    env = Envelope(id=new_ulid(), type="job.event", event_seq=1, payload={})
    assert env.event_seq == 1
