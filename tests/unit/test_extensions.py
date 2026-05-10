"""Tests for extension namespacing and unknown-message handling (RFC §21)."""

from __future__ import annotations

import pytest

from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode
from arcp.extensions import (
    ExtensionRegistry,
    classify_unknown,
    is_core_type,
    is_extension_name,
    validate_extension_name,
)


@pytest.mark.parametrize(
    "name",
    [
        "arcpx.acme.workflow.v1",
        "arcpx.example.thing.v9",
        "com.acme.workflow.v2",
        "arcpx.example.runtime.v1",
    ],
)
def test_valid_extension_names(name: str) -> None:
    assert is_extension_name(name)
    validate_extension_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "x-experimental",
        "arcpx",
        "arcpx.acme",
        "arcpx.acme.no-version",
        "session.open",
        "tool.invoke",
        "no.dot.suffix",
        "com.acme.thing",
    ],
)
def test_invalid_extension_names(name: str) -> None:
    assert not is_extension_name(name)
    with pytest.raises(ARCPError) as exc:
        validate_extension_name(name)
    assert exc.value.code == ErrorCode.INVALID_ARGUMENT


@pytest.mark.parametrize(
    "name",
    [
        "session.open",
        "job.completed",
        "tool.error",
        "stream.chunk",
        "human.input.request",
        "permission.grant",
        "lease.revoked",
        "subscribe",
        "subscribe.event",
        "subscription.backfill_complete",
        "artifact.put",
        "event.emit",
        "trace.span",
        "checkpoint.create",
        "agent.delegate",
        "workflow.start",
        "ping",
        "pong",
        "ack",
        "nack",
        "cancel",
        "interrupt",
        "resume",
        "backpressure",
        "log",
        "metric",
    ],
)
def test_core_types(name: str) -> None:
    assert is_core_type(name)


def test_unknown_core_type_yields_nack() -> None:
    env = Envelope.model_validate({"id": "m", "type": "tool.bogus"})
    decision = classify_unknown(env, ExtensionRegistry())
    assert decision.action == "nack"


def test_unknown_namespaced_optional_drops() -> None:
    env = Envelope.model_validate(
        {"id": "m", "type": "arcpx.acme.thing.v1", "extensions": {"optional": True}}
    )
    decision = classify_unknown(env, ExtensionRegistry())
    assert decision.action == "drop"


def test_unknown_namespaced_required_nacks() -> None:
    env = Envelope.model_validate({"id": "m", "type": "arcpx.acme.thing.v1"})
    decision = classify_unknown(env, ExtensionRegistry())
    assert decision.action == "nack"


def test_advertised_namespaced_handler_missing_nacks() -> None:
    reg = ExtensionRegistry()
    reg.advertise("arcpx.acme.thing.v1")
    env = Envelope.model_validate(
        {"id": "m", "type": "arcpx.acme.thing.v1", "extensions": {"optional": True}}
    )
    # Even with optional=true, advertised but unhandled -> nack.
    assert classify_unknown(env, reg).action == "nack"


def test_unrecognized_neither_core_nor_extension_nacks() -> None:
    env = Envelope.model_validate({"id": "m", "type": "weirdthing"})
    assert classify_unknown(env, ExtensionRegistry()).action == "nack"


def test_advertise_rejects_invalid_name() -> None:
    reg = ExtensionRegistry()
    with pytest.raises(ARCPError):
        reg.advertise("x-bogus")


def test_advertise_subnamespace_match() -> None:
    reg = ExtensionRegistry()
    reg.advertise("arcpx.acme.thing.v1")
    assert reg.is_advertised("arcpx.acme.thing.detail")
    assert not reg.is_advertised("arcpx.other.thing.detail")
