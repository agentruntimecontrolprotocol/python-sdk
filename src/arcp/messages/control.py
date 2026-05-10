"""Control-plane message payloads (RFC §6.2 control)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nonce: str | None = None


class PongPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nonce: str | None = None


class AckPayload(BaseModel):
    """Ack of a previously received command. ``correlation_id`` carries on the envelope."""

    model_config = ConfigDict(extra="forbid")
    note: str | None = None


class NackPayload(BaseModel):
    """Refusal envelope; mirrors the §18.1 error shape."""

    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    retryable: bool | None = None
    details: dict[str, Any] | None = None


CancelTarget = Literal["job", "stream", "session"]


class CancelPayload(BaseModel):
    """Cooperative cancellation request (§10.4)."""

    model_config = ConfigDict(extra="forbid")
    target: CancelTarget
    target_id: str
    reason: str | None = None
    deadline_ms: int = Field(default=5000, ge=0)


class CancelAcceptedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: CancelTarget
    target_id: str


class CancelRefusedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: CancelTarget
    target_id: str
    code: str
    message: str


class InterruptPayload(BaseModel):
    """Pause-and-ask request (§10.5)."""

    model_config = ConfigDict(extra="forbid")
    target: Literal["job"]
    target_id: str
    prompt: str


class ResumePayload(BaseModel):
    """Resume after disconnect or pause (§19)."""

    model_config = ConfigDict(extra="forbid")
    after_message_id: str | None = None
    checkpoint_id: str | None = None
    include_open_streams: bool = True


class BackpressurePayload(BaseModel):
    """Backpressure signal for streams (§11.2)."""

    model_config = ConfigDict(extra="forbid")
    desired_rate_per_second: int | None = None
    buffer_remaining_bytes: int | None = None
    reason: str | None = None


class CheckpointCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None


class CheckpointRestorePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checkpoint_id: str


PAYLOADS: dict[str, type[BaseModel]] = {
    "ping": PingPayload,
    "pong": PongPayload,
    "ack": AckPayload,
    "nack": NackPayload,
    "cancel": CancelPayload,
    "cancel.accepted": CancelAcceptedPayload,
    "cancel.refused": CancelRefusedPayload,
    "interrupt": InterruptPayload,
    "resume": ResumePayload,
    "backpressure": BackpressurePayload,
    "checkpoint.create": CheckpointCreatePayload,
    "checkpoint.restore": CheckpointRestorePayload,
}


__all__ = [
    "PAYLOADS",
    "AckPayload",
    "BackpressurePayload",
    "CancelAcceptedPayload",
    "CancelPayload",
    "CancelRefusedPayload",
    "CancelTarget",
    "CheckpointCreatePayload",
    "CheckpointRestorePayload",
    "InterruptPayload",
    "NackPayload",
    "PingPayload",
    "PongPayload",
    "ResumePayload",
]
