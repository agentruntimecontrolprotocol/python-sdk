"""Tests for the canonical envelope (RFC §6.1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp.envelope import Envelope


def _minimal(**overrides: object) -> Envelope:
    base: dict[str, object] = {"id": "msg_1", "type": "ping"}
    base.update(overrides)
    return Envelope.model_validate(base)


def test_envelope_minimum_required_fields() -> None:
    env = _minimal()
    assert env.arcp == "1.0"
    assert env.priority == "normal"
    assert env.timestamp.endswith("Z")


def test_envelope_round_trip_preserves_all_fields() -> None:
    raw: dict[str, object] = {
        "arcp": "1.0",
        "id": "msg_1",
        "type": "job.progress",
        "timestamp": "2026-05-09T13:42:11Z",
        "source": "client",
        "target": "runtime",
        "session_id": "sess_1",
        "job_id": "job_1",
        "stream_id": "str_1",
        "subscription_id": "sub_1",
        "trace_id": "trace_1",
        "span_id": "span_1",
        "parent_span_id": "span_0",
        "correlation_id": "msg_0",
        "causation_id": "msg_0",
        "idempotency_key": "intent_1",
        "priority": "high",
        "extensions": {"arcpx.acme.flag": True, "optional": True},
        "payload": {"percent": 42},
    }
    env = Envelope.from_wire(raw)
    assert env.to_wire() == raw


def test_envelope_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        Envelope.model_validate({"id": "m", "type": "ping", "wat": True})


def test_envelope_rejects_invalid_priority() -> None:
    with pytest.raises(ValidationError):
        Envelope.model_validate({"id": "m", "type": "ping", "priority": "ultra"})


def test_envelope_rejects_invalid_timestamp() -> None:
    with pytest.raises(ValidationError):
        Envelope.model_validate({"id": "m", "type": "ping", "timestamp": "yesterday"})


def test_envelope_omits_none_fields_on_wire() -> None:
    wire = _minimal().to_wire()
    assert "session_id" not in wire
    assert "extensions" not in wire
    assert wire["payload"] == {}


def test_envelope_extensions_are_preserved_verbatim() -> None:
    extensions = {"arcpx.acme.foo.v1": {"nested": [1, 2]}, "optional": False}
    env = _minimal(extensions=extensions)
    assert env.to_wire()["extensions"] == extensions


def test_envelope_priority_default_is_normal() -> None:
    assert _minimal().priority == "normal"


def test_envelope_payload_default_is_empty_dict() -> None:
    assert _minimal().payload == {}


def test_envelope_timestamp_with_offset_is_accepted() -> None:
    env = Envelope.model_validate(
        {"id": "m", "type": "ping", "timestamp": "2026-05-09T13:42:11+00:00"}
    )
    assert "2026-05-09" in env.timestamp
