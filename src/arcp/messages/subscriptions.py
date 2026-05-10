"""Subscription payloads (RFC §13)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from arcp.envelope import Priority


class SubscribeFilter(BaseModel):
    """Subscription filter expression (§13.2)."""

    model_config = ConfigDict(extra="forbid")
    session_id: list[str] | None = None
    trace_id: list[str] | None = None
    job_id: list[str] | None = None
    stream_id: list[str] | None = None
    types: list[str] | None = None
    min_priority: Priority | None = None


class SubscribeSince(BaseModel):
    model_config = ConfigDict(extra="forbid")
    after_message_id: str | None = None


class SubscribePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filter: SubscribeFilter = Field(default_factory=SubscribeFilter)
    since: SubscribeSince | None = None


class SubscribeAcceptedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscription_id: str


class SubscribeEventPayload(BaseModel):
    """Carries the original envelope as ``event`` (§13.1)."""

    model_config = ConfigDict(extra="forbid")
    event: dict[str, Any]


class UnsubscribePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscription_id: str


class SubscribeClosedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscription_id: str
    code: str
    reason: str | None = None


# Synthetic event type emitted at the boundary between backfill and live tail.
BACKFILL_COMPLETE_TYPE = "subscription.backfill_complete"


class SubscriptionBackfillCompletePayload(BaseModel):
    """Payload of the synthetic backfill-complete event (§13.3)."""

    model_config = ConfigDict(extra="forbid")
    subscription_id: str
    event_count: int = Field(ge=0)
    boundary: Literal["historical_to_live"] = "historical_to_live"


PAYLOADS: dict[str, type[BaseModel]] = {
    "subscribe": SubscribePayload,
    "subscribe.accepted": SubscribeAcceptedPayload,
    "subscribe.event": SubscribeEventPayload,
    "unsubscribe": UnsubscribePayload,
    "subscribe.closed": SubscribeClosedPayload,
    BACKFILL_COMPLETE_TYPE: SubscriptionBackfillCompletePayload,
}


__all__ = [
    "BACKFILL_COMPLETE_TYPE",
    "PAYLOADS",
    "SubscribeAcceptedPayload",
    "SubscribeClosedPayload",
    "SubscribeEventPayload",
    "SubscribeFilter",
    "SubscribePayload",
    "SubscribeSince",
    "SubscriptionBackfillCompletePayload",
    "UnsubscribePayload",
]
