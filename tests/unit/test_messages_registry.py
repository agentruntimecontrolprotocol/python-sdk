"""Tests for the message-type → payload model registry."""

from __future__ import annotations

import pytest

from arcp.messages import PAYLOAD_MODELS, validate_payload


def test_registry_covers_core_types() -> None:
    expected = {
        # session
        "session.open",
        "session.challenge",
        "session.authenticate",
        "session.accepted",
        "session.unauthenticated",
        "session.rejected",
        "session.refresh",
        "session.evicted",
        "session.close",
        # control
        "ping",
        "pong",
        "ack",
        "nack",
        "cancel",
        "cancel.accepted",
        "cancel.refused",
        "interrupt",
        "resume",
        "backpressure",
        "checkpoint.create",
        "checkpoint.restore",
        # execution
        "tool.invoke",
        "tool.result",
        "tool.error",
        "job.accepted",
        "job.started",
        "job.progress",
        "job.heartbeat",
        "job.checkpoint",
        "job.completed",
        "job.failed",
        "job.cancelled",
        "job.schedule",
        "workflow.start",
        "workflow.complete",
        "agent.delegate",
        "agent.handoff",
        # streaming
        "stream.open",
        "stream.chunk",
        "stream.close",
        "stream.error",
        # human
        "human.input.request",
        "human.input.response",
        "human.choice.request",
        "human.choice.response",
        "human.input.cancelled",
        # permissions
        "permission.request",
        "permission.grant",
        "permission.deny",
        "lease.granted",
        "lease.extended",
        "lease.revoked",
        "lease.refresh",
        # subscriptions
        "subscribe",
        "subscribe.accepted",
        "subscribe.event",
        "unsubscribe",
        "subscribe.closed",
        "subscription.backfill_complete",
        # artifacts
        "artifact.put",
        "artifact.fetch",
        "artifact.ref",
        "artifact.release",
        # telemetry
        "event.emit",
        "log",
        "metric",
        "trace.span",
    }
    missing = expected - set(PAYLOAD_MODELS.keys())
    assert missing == set(), f"missing message types: {missing}"


def test_validate_payload_returns_none_for_unknown_type() -> None:
    assert validate_payload("arcpx.unknown.thing.v1", {"x": 1}) is None


def test_validate_payload_rejects_bad_payload() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        validate_payload("ping", {"unknown": True})
