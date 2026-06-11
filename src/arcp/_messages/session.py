"""Session-level message payloads (spec §6)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ISO8601_UTC_HINT = "ISO 8601 UTC, e.g. 2026-05-14T12:00:00Z"


class ClientInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    version: str


class RuntimeInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    version: str


class AuthBearer(BaseModel):
    scheme: Literal["bearer"] = "bearer"
    token: str


class AgentInventoryEntry(BaseModel):
    """Rich agent shape for `welcome.capabilities.agents` (§7.5)."""

    model_config = ConfigDict(extra="allow")
    name: str
    versions: tuple[str, ...] = ()
    default: str | None = None


class Capabilities(BaseModel):
    """Hello/welcome capabilities envelope."""

    model_config = ConfigDict(extra="allow")
    encodings: tuple[str, ...] = ("json",)
    features: tuple[str, ...] = ()
    # Either flat list[str] (v1.0 fallback) or rich list[AgentInventoryEntry] (v1.1).
    agents: tuple[str, ...] | tuple[AgentInventoryEntry, ...] = ()


class SessionResume(BaseModel):
    session_id: str
    resume_token: str
    last_event_seq: int = Field(ge=0)


class SessionHelloPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    client: ClientInfo
    auth: AuthBearer
    capabilities: Capabilities = Field(default_factory=Capabilities)
    resume: SessionResume | None = None


class SessionWelcomePayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    runtime: RuntimeInfo
    session_id: str
    resume_token: str
    resume_window_sec: int = Field(default=600, ge=0)
    heartbeat_interval_sec: int | None = None
    capabilities: Capabilities = Field(default_factory=Capabilities)
    # §6.2 does not define `accepted_at`; keep it optional so a conformant
    # runtime that omits it still validates. The SDK still emits it outbound.
    accepted_at: str | None = None


class SessionClosePayload(BaseModel):
    """Client request to close the session gracefully (§6.7)."""

    model_config = ConfigDict(extra="allow")
    reason: str
    code: str | None = None


# Backward-compatible alias for the prior `session.bye` payload shape.
SessionByePayload = SessionClosePayload


class SessionClosedPayload(BaseModel):
    """Runtime acknowledgement of `session.close` (§6.7)."""

    model_config = ConfigDict(extra="allow")
    reason: str | None = None


class SessionErrorPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None


class SessionPingPayload(BaseModel):
    nonce: str
    sent_at: str


class SessionPongPayload(BaseModel):
    ping_nonce: str
    received_at: str


class SessionAckPayload(BaseModel):
    last_processed_seq: int = Field(ge=0)


class ListJobsFilter(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: tuple[str, ...] | None = None
    agent: str | None = None
    created_after: str | None = None


class SessionListJobsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    filter: ListJobsFilter | None = None
    limit: int | None = Field(default=None, ge=1, le=1000)
    cursor: str | None = None


class JobListEntry(BaseModel):
    model_config = ConfigDict(extra="allow")
    job_id: str
    agent: str
    status: str
    submitted_at: str
    parent_job_id: str | None = None
    trace_id: str | None = None


class SessionJobsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    request_id: str
    jobs: tuple[JobListEntry, ...] = ()
    next_cursor: str | None = None


__all__ = (
    "AgentInventoryEntry",
    "AuthBearer",
    "Capabilities",
    "ClientInfo",
    "JobListEntry",
    "ListJobsFilter",
    "RuntimeInfo",
    "SessionAckPayload",
    "SessionByePayload",
    "SessionClosePayload",
    "SessionClosedPayload",
    "SessionErrorPayload",
    "SessionHelloPayload",
    "SessionJobsPayload",
    "SessionListJobsPayload",
    "SessionPingPayload",
    "SessionPongPayload",
    "SessionResume",
    "SessionWelcomePayload",
)
