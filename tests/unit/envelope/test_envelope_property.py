"""Hypothesis property: envelope round-trips through JSON-equivalent dicts."""

from __future__ import annotations

from hypothesis import given, settings

from arcp import Envelope
from tests._strategies import envelope_payloads, trace_id_strategy, ulid_strategy


@given(
    eid=ulid_strategy(),
    payload=envelope_payloads(),
    trace=trace_id_strategy(),
)
@settings(max_examples=50, deadline=None)
def test_envelope_property_roundtrip(eid: str, payload: dict[str, object], trace: str) -> None:
    env = Envelope(id=eid, type="session.ping", trace_id=trace, payload=payload)
    wire = env.to_wire()
    env2 = Envelope.from_wire(wire)
    assert env2.model_dump(exclude_none=True) == env.model_dump(exclude_none=True)
