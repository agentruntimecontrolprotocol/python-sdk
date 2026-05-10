"""Identity and authentication payloads (RFC §8)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AuthScheme = Literal["bearer", "mtls", "oauth2", "signed_jwt", "none"]
TrustLevel = Literal["untrusted", "constrained", "trusted", "privileged"]


class Identity(BaseModel):
    """Client or runtime identity block (§8.2, §8.3)."""

    model_config = ConfigDict(extra="forbid")
    kind: str
    version: str
    fingerprint: str | None = None
    principal: str | None = None
    trust_level: TrustLevel | None = None


class AuthBlock(BaseModel):
    """Credential block carried on session.open / session.authenticate."""

    model_config = ConfigDict(extra="forbid")
    scheme: AuthScheme
    token: str | None = None


class Capabilities(BaseModel):
    """Capability set negotiated during handshake (§7).

    The model accepts arbitrary additional booleans/values so deployments can
    surface custom capability flags; absent boolean keys are treated as
    ``False`` per §7.
    """

    model_config = ConfigDict(extra="allow")
    streaming: bool = False
    durable_jobs: bool = False
    checkpoints: bool = False
    binary_streams: bool = False
    binary_encoding: list[str] | None = None
    agent_handoff: bool = False
    human_input: bool = False
    artifacts: bool = False
    subscriptions: bool = False
    scheduled_jobs: bool = False
    interrupt: bool = False
    anonymous: bool = False
    heartbeat_interval_seconds: int = 30
    heartbeat_recovery: Literal["fail", "block"] = "fail"
    artifact_retention: dict[str, int] | None = None
    extensions: list[str] = Field(default_factory=list)


class SessionOpenPayload(BaseModel):
    """``session open`` payload."""

    model_config = ConfigDict(extra="forbid")
    auth: AuthBlock
    client: Identity
    capabilities: Capabilities


class SessionChallengePayload(BaseModel):
    """``session challenge`` payload."""

    model_config = ConfigDict(extra="forbid")
    nonce: str
    method: Literal["challenge_response"] = "challenge_response"
    expires_at: str | None = None


class SessionAuthenticatePayload(BaseModel):
    """``session authenticate`` payload."""

    model_config = ConfigDict(extra="forbid")
    auth: AuthBlock
    nonce_response: str | None = None


class RuntimeIdentity(Identity):
    """Identity block emitted by the runtime in session.accepted."""


class LeaseBlock(BaseModel):
    """Lease block."""

    model_config = ConfigDict(extra="forbid")
    expires_at: str


class SessionAcceptedPayload(BaseModel):
    """``session accepted`` payload."""

    model_config = ConfigDict(extra="forbid")
    session_id: str
    runtime: RuntimeIdentity
    capabilities: Capabilities
    lease: LeaseBlock | None = None


class SessionUnauthenticatedPayload(BaseModel):
    """Emitted when a non-handshake message arrives before session.accepted."""

    model_config = ConfigDict(extra="forbid")
    code: str = "UNAUTHENTICATED"
    message: str


class SessionRejectedPayload(BaseModel):
    """``session rejected`` payload."""

    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    details: dict[str, Any] | None = None


class SessionRefreshPayload(BaseModel):
    """``session refresh`` payload."""

    model_config = ConfigDict(extra="forbid")
    nonce: str
    expires_at: str


class SessionEvictedPayload(BaseModel):
    """``session evicted`` payload."""

    model_config = ConfigDict(extra="forbid")
    code: str
    reason: str
    message: str | None = None


class SessionClosePayload(BaseModel):
    """``session close`` payload."""

    model_config = ConfigDict(extra="forbid")
    reason: str | None = None
    detach_jobs: bool = False


PAYLOADS: dict[str, type[BaseModel]] = {
    "session.open": SessionOpenPayload,
    "session.challenge": SessionChallengePayload,
    "session.authenticate": SessionAuthenticatePayload,
    "session.accepted": SessionAcceptedPayload,
    "session.unauthenticated": SessionUnauthenticatedPayload,
    "session.rejected": SessionRejectedPayload,
    "session.refresh": SessionRefreshPayload,
    "session.evicted": SessionEvictedPayload,
    "session.close": SessionClosePayload,
}


__all__ = [
    "PAYLOADS",
    "AuthBlock",
    "AuthScheme",
    "Capabilities",
    "Identity",
    "LeaseBlock",
    "RuntimeIdentity",
    "SessionAcceptedPayload",
    "SessionAuthenticatePayload",
    "SessionChallengePayload",
    "SessionClosePayload",
    "SessionEvictedPayload",
    "SessionOpenPayload",
    "SessionRefreshPayload",
    "SessionRejectedPayload",
    "SessionUnauthenticatedPayload",
    "TrustLevel",
]
