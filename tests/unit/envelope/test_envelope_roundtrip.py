"""§5.1 — `from_wire(to_wire(env))` preserves typed envelopes."""

from __future__ import annotations

import pytest

from arcp import Envelope
from arcp._ulid import new_envelope_id, new_job_id, new_session_id


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "session.hello", "payload": {"client": {"name": "x", "version": "0"}}},
        {
            "type": "job.event",
            "session_id": new_session_id(),
            "job_id": new_job_id(),
            "event_seq": 1,
            "payload": {"kind": "log", "ts": "2026-05-14T12:00:00Z", "body": {}},
        },
        {
            "type": "session.welcome",
            "session_id": new_session_id(),
            "trace_id": "0af7651916cd43dd8448eb211c80319c",
            "payload": {"runtime": {"name": "r", "version": "0"}},
        },
    ],
)
def test_envelope_roundtrip(kwargs: dict[str, object]) -> None:
    env = Envelope(id=new_envelope_id(), **kwargs)  # type: ignore[arg-type]
    wire = env.to_wire()
    env2 = Envelope.from_wire(wire)
    assert env2.model_dump(exclude_none=True) == env.model_dump(exclude_none=True)
