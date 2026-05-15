"""Wire-message type registry: `type` string -> pydantic payload model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .execution import (
    JobAcceptedPayload,
    JobCancelPayload,
    JobErrorPayload,
    JobEventPayload,
    JobResultPayload,
    JobSubmitPayload,
    JobSubscribedPayload,
    JobSubscribePayload,
    JobUnsubscribePayload,
)
from .session import (
    SessionAckPayload,
    SessionByePayload,
    SessionErrorPayload,
    SessionHelloPayload,
    SessionJobsPayload,
    SessionListJobsPayload,
    SessionPingPayload,
    SessionPongPayload,
    SessionWelcomePayload,
)

PAYLOAD_REGISTRY: dict[str, type[BaseModel]] = {
    "session.hello": SessionHelloPayload,
    "session.welcome": SessionWelcomePayload,
    "session.bye": SessionByePayload,
    "session.error": SessionErrorPayload,
    "session.ping": SessionPingPayload,
    "session.pong": SessionPongPayload,
    "session.ack": SessionAckPayload,
    "session.list_jobs": SessionListJobsPayload,
    "session.jobs": SessionJobsPayload,
    "job.submit": JobSubmitPayload,
    "job.accepted": JobAcceptedPayload,
    "job.cancel": JobCancelPayload,
    "job.event": JobEventPayload,
    "job.result": JobResultPayload,
    "job.error": JobErrorPayload,
    "job.subscribe": JobSubscribePayload,
    "job.subscribed": JobSubscribedPayload,
    "job.unsubscribe": JobUnsubscribePayload,
}


def parse_payload(envelope_type: str, raw: dict[str, Any]) -> BaseModel | dict[str, Any]:
    """Parse a payload dict into its typed model; unknown types pass through."""
    cls = PAYLOAD_REGISTRY.get(envelope_type)
    if cls is None:
        return raw
    return cls.model_validate(raw)


__all__ = ("PAYLOAD_REGISTRY", "parse_payload")
