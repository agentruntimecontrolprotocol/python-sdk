"""Unit tests for arcp._messages payload registry and parse_payload."""

from __future__ import annotations

from arcp._messages import PAYLOAD_REGISTRY, parse_payload
from arcp._messages.session import SessionHelloPayload


def test_payload_registry_has_known_types() -> None:
    for key in (
        "session.hello",
        "session.welcome",
        "session.bye",
        "session.error",
        "session.ping",
        "session.pong",
        "job.submit",
        "job.accepted",
        "job.event",
        "job.result",
        "job.error",
    ):
        assert key in PAYLOAD_REGISTRY, f"missing: {key}"


def test_parse_payload_known_type_returns_model() -> None:
    raw = {
        "client": {"name": "c", "version": "1"},
        "auth": {"scheme": "bearer", "token": "tok"},
        "capabilities": {"encodings": ["json"], "features": []},
    }
    result = parse_payload("session.hello", raw)
    assert isinstance(result, SessionHelloPayload)


def test_parse_payload_unknown_type_returns_raw_dict() -> None:
    raw = {"foo": "bar", "baz": 42}
    result = parse_payload("x-vendor.custom.thing", raw)
    # Unknown type must pass through as the original dict
    assert result is raw
    assert result == {"foo": "bar", "baz": 42}


def test_parse_payload_another_known_type() -> None:
    from arcp._messages.execution import JobResultPayload

    raw = {
        "final_status": "success",
        "result": {"ok": True},
        "completed_at": "2024-01-01T00:00:00Z",
    }
    result = parse_payload("job.result", raw)
    assert isinstance(result, JobResultPayload)
    assert result.final_status == "success"
