"""Canonical ARCP envelope (RFC §6.1).

Every ARCP message is an instance of :class:`Envelope`. The envelope is
schema-validated by Pydantic; payloads stay typed as ``dict[str, Any]`` here so
that the message-type registry (see ``arcp.messages``) can layer payload-specific
schemas on top without forcing this module to import every payload model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

Priority = Literal["low", "normal", "high", "critical"]


def _utcnow_iso() -> str:
    """Return current UTC time formatted per RFC 3339 (``Z`` suffix)."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Envelope(BaseModel):
    """Canonical ARCP message envelope (RFC §6.1.1).

    Field semantics follow the table in §6.1.1 verbatim. The ``payload`` field is
    intentionally untyped at this layer; type-specific validation is performed by
    the dispatcher when it routes by ``type``.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=False)

    arcp: str = Field(default="1.0", description="Protocol version understood by the sender.")
    id: str = Field(description="Globally unique message id; transport-level idempotency key.")
    type: str = Field(description="Message type, e.g. 'tool.invoke' or a namespaced extension.")
    timestamp: str = Field(default_factory=_utcnow_iso, description="Sender RFC 3339 timestamp.")
    source: str | None = None
    target: str | None = None
    session_id: str | None = None
    job_id: str | None = None
    stream_id: str | None = None
    subscription_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    idempotency_key: str | None = None
    priority: Priority = "normal"
    extensions: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, value: str) -> str:
        # Accept any RFC 3339 string parseable by ``datetime.fromisoformat`` after
        # rewriting the trailing ``Z`` to ``+00:00`` (Python <3.11 quirk preserved
        # for safety; harmless on 3.12+).
        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        try:
            datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"timestamp is not a valid RFC 3339 string: {value!r}") from exc
        return value

    @field_serializer("priority")
    def _serialize_priority(self, value: Priority) -> Priority:
        return value

    def to_wire(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict, omitting ``None`` optional fields."""
        return self.model_dump(exclude_none=True, by_alias=False)

    @classmethod
    def from_wire(cls, raw: dict[str, Any]) -> Envelope:
        """Parse a wire-format dict into an :class:`Envelope`."""
        return cls.model_validate(raw)


def new_message_id() -> str:
    """Mint an opaque, globally-unique message id (transport idempotency key)."""
    import uuid

    return f"msg_{uuid.uuid4().hex[:12]}"


__all__ = ["Envelope", "Priority", "new_message_id"]
