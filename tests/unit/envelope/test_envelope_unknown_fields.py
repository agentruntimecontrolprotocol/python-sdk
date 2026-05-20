"""§5.1 — unknown top-level fields are preserved on inbound deserialization."""

from __future__ import annotations

from arcp import Envelope
from arcp._ulid import new_ulid


def test_unknown_field_passes_through() -> None:
    raw = {
        "arcp": "1.1",
        "id": new_ulid(),
        "type": "session.ping",
        "payload": {"nonce": "abc", "sent_at": "2026-05-14T12:00:00Z"},
        "x-vendor.extra": {"foo": "bar"},
    }
    env = Envelope.from_wire(raw)
    # The model_config sets extra="allow"; the extra field is present on the
    # model dump.
    dumped = env.model_dump(exclude_none=True)
    assert dumped.get("x-vendor.extra") == {"foo": "bar"}


def test_roundtrip_preserves_unknown_field() -> None:
    raw = {
        "arcp": "1.1",
        "id": new_ulid(),
        "type": "session.ping",
        "payload": {},
        "x-vendor.flag": True,
    }
    env = Envelope.from_wire(raw)
    wire = env.to_wire()
    assert wire.get("x-vendor.flag") is True
