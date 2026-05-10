"""Session lifecycle and handshake (RFC §8, §9).

Implements the four-step handshake from §8.1:

1. Client → ``session.open``.
2. Runtime → ``session.challenge`` (optional) | ``session.accepted`` |
   ``session.rejected``.
3. Client → ``session.authenticate`` (only after challenge).
4. Runtime → ``session.accepted`` | ``session.rejected``.

Until ``session.accepted`` is delivered, runtimes drop and log non-handshake
messages (§8.1).
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode
from arcp.extensions import ExtensionRegistry, validate_extension_name
from arcp.messages.session import (
    AuthBlock,
    Capabilities,
    Identity,
    LeaseBlock,
    RuntimeIdentity,
    SessionAcceptedPayload,
    SessionAuthenticatePayload,
    SessionChallengePayload,
    SessionOpenPayload,
    SessionRejectedPayload,
)
from arcp.runtime.pending import PendingRequestRegistry


class SessionPhase(StrEnum):
    """Internal session FSM (PLAN.md §3.1)."""

    OPENING = "opening"
    CHALLENGING = "challenging"
    AUTHENTICATING = "authenticating"
    ACCEPTED = "accepted"
    REFRESHING = "refreshing"
    EVICTED = "evicted"
    CLOSED = "closed"
    REJECTED = "rejected"


@dataclass
class SessionState:
    """Per-session bookkeeping."""

    session_id: str
    principal: str
    client_identity: Identity
    runtime_identity: RuntimeIdentity
    capabilities: Capabilities
    extensions: ExtensionRegistry
    phase: SessionPhase = SessionPhase.ACCEPTED
    pending: PendingRequestRegistry = field(default_factory=PendingRequestRegistry)
    state: dict[str, Any] = field(default_factory=dict[str, Any])
    expires_at: str | None = None


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _format_iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class HandshakeResult:
    """Outcome of a handshake driven by the runtime."""

    state: SessionState | None
    response: Envelope


def negotiate_capabilities(
    requested: Capabilities, advertised: Capabilities
) -> tuple[Capabilities, str | None]:
    """Intersect requested and advertised capability sets per §7.

    Returns ``(intersection, rejection_reason | None)``. A non-None reason
    indicates a required-but-unsupported capability and the runtime should
    emit ``session.rejected`` with ``code: UNIMPLEMENTED`` per §7.
    """

    boolean_caps = (
        "streaming",
        "durable_jobs",
        "checkpoints",
        "binary_streams",
        "agent_handoff",
        "human_input",
        "artifacts",
        "subscriptions",
        "scheduled_jobs",
        "interrupt",
        "anonymous",
    )

    accepted: dict[str, Any] = {}
    rejection: str | None = None
    for cap in boolean_caps:
        want = bool(getattr(requested, cap))
        have = bool(getattr(advertised, cap))
        if want and not have:
            rejection = f"capability {cap!r} is required but not supported"
            break
        accepted[cap] = want and have

    if rejection is not None:
        return advertised, rejection

    accepted["heartbeat_interval_seconds"] = advertised.heartbeat_interval_seconds
    accepted["heartbeat_recovery"] = advertised.heartbeat_recovery
    accepted["binary_encoding"] = advertised.binary_encoding or ["base64"]
    accepted["artifact_retention"] = advertised.artifact_retention

    # Validate extension namespaces and intersect.
    accepted_extensions: list[str] = []
    for ext in requested.extensions:
        try:
            validate_extension_name(ext)
        except ARCPError:
            rejection = f"extension {ext!r} has invalid namespace"
            break
        if ext in advertised.extensions:
            accepted_extensions.append(ext)
        else:
            rejection = f"extension {ext!r} not supported"
            break

    if rejection is not None:
        return advertised, rejection

    accepted["extensions"] = accepted_extensions
    return Capabilities.model_validate(accepted), None


@dataclass
class HandshakeDriver:
    """Server-side handshake driver.

    The driver keeps no state across invocations; each ``open`` →
    ``challenge`` → ``authenticate`` chain operates on the values flowing
    through the dispatch loop.
    """

    runtime_identity: RuntimeIdentity
    advertised: Capabilities
    bearer_validator: Any | None = None  # arcp.auth.bearer.TokenValidator
    jwt_validator: Any | None = None  # arcp.auth.jwt.JWTValidator
    challenge_lifetime_seconds: int = 60
    session_lifetime_seconds: int = 3600

    def __post_init__(self) -> None:
        self._challenges: dict[str, dict[str, Any]] = {}

    def handle_open(self, envelope: Envelope) -> HandshakeResult:
        """Process a ``session.open`` envelope."""

        try:
            payload = SessionOpenPayload.model_validate(envelope.payload)
        except Exception as exc:  # pydantic ValidationError
            return HandshakeResult(
                state=None, response=self._reject(envelope, ErrorCode.INVALID_ARGUMENT, str(exc))
            )

        capabilities, rejection = negotiate_capabilities(payload.capabilities, self.advertised)
        if rejection is not None:
            return HandshakeResult(
                state=None,
                response=self._reject(envelope, ErrorCode.UNIMPLEMENTED, rejection),
            )

        # Decide whether to challenge or accept directly. v0.1 challenges only
        # when scheme is signed_jwt without a token attached, or when bearer
        # is present but the runtime wants to confirm freshness. The reference
        # logic is: bearer/signed_jwt without challenge round-trip → validate
        # eagerly. ``none`` requires negotiated anonymous capability.
        scheme = payload.auth.scheme
        if scheme == "none":
            if not capabilities.anonymous:
                return HandshakeResult(
                    state=None,
                    response=self._reject(
                        envelope,
                        ErrorCode.UNAUTHENTICATED,
                        "anonymous mode not negotiated",
                    ),
                )
            principal = payload.client.principal or "anonymous"
            state = self._materialize_session(envelope, payload, capabilities, principal)
            return HandshakeResult(state=state, response=self._accept(envelope, state))

        if scheme in ("bearer", "signed_jwt"):
            try:
                principal = self._validate_token(payload.auth)
            except ARCPError as exc:
                return HandshakeResult(
                    state=None,
                    response=self._reject(envelope, exc.code, exc.message),
                )
            state = self._materialize_session(envelope, payload, capabilities, principal)
            return HandshakeResult(state=state, response=self._accept(envelope, state))

        if scheme in ("mtls", "oauth2"):
            return HandshakeResult(
                state=None,
                response=self._reject(
                    envelope,
                    ErrorCode.UNIMPLEMENTED,
                    f"auth scheme {scheme!r} not supported in v0.1",
                ),
            )

        return HandshakeResult(
            state=None,
            response=self._reject(envelope, ErrorCode.INVALID_ARGUMENT, "unknown auth scheme"),
        )

    def issue_challenge(self, opening: Envelope) -> Envelope:
        """Manually issue a challenge for a session.open envelope.

        Reserved for runtimes that always challenge; the default handler
        does not call this. Kept for completeness.
        """

        nonce = secrets.token_urlsafe(16)
        self._challenges[opening.id] = {
            "nonce": nonce,
            "expires_at": _now() + timedelta(seconds=self.challenge_lifetime_seconds),
        }
        challenge = SessionChallengePayload(
            nonce=nonce,
            expires_at=_format_iso(_now() + timedelta(seconds=self.challenge_lifetime_seconds)),
        )
        return Envelope(
            id=_new_id("msg"),
            type="session.challenge",
            correlation_id=opening.id,
            payload=challenge.model_dump(),
        )

    def _validate_token(self, auth: AuthBlock) -> str:
        if auth.token is None:
            raise ARCPError(ErrorCode.UNAUTHENTICATED, "missing token")
        if auth.scheme == "bearer":
            if self.bearer_validator is None:
                raise ARCPError(ErrorCode.UNIMPLEMENTED, "bearer auth not configured")
            return self.bearer_validator.validate(auth.token)
        if auth.scheme == "signed_jwt":
            if self.jwt_validator is None:
                raise ARCPError(ErrorCode.UNIMPLEMENTED, "signed_jwt not configured")
            return self.jwt_validator.validate(auth.token)
        raise ARCPError(ErrorCode.INVALID_ARGUMENT, f"unsupported scheme {auth.scheme!r}")

    def _materialize_session(
        self,
        envelope: Envelope,
        payload: SessionOpenPayload,
        capabilities: Capabilities,
        principal: str,
    ) -> SessionState:
        session_id = _new_id("sess")
        registry = ExtensionRegistry()
        for ext in capabilities.extensions:
            registry.advertise(ext)
        expires = _now() + timedelta(seconds=self.session_lifetime_seconds)
        return SessionState(
            session_id=session_id,
            principal=principal,
            client_identity=payload.client,
            runtime_identity=self.runtime_identity,
            capabilities=capabilities,
            extensions=registry,
            phase=SessionPhase.ACCEPTED,
            expires_at=_format_iso(expires),
        )

    def _accept(self, envelope: Envelope, state: SessionState) -> Envelope:
        accepted = SessionAcceptedPayload(
            session_id=state.session_id,
            runtime=state.runtime_identity,
            capabilities=state.capabilities,
            lease=LeaseBlock(expires_at=state.expires_at or _format_iso(_now())),
        )
        return Envelope(
            id=_new_id("msg"),
            type="session.accepted",
            correlation_id=envelope.id,
            session_id=state.session_id,
            payload=accepted.model_dump(),
        )

    def _reject(self, envelope: Envelope, code: ErrorCode, message: str) -> Envelope:
        rejected = SessionRejectedPayload(code=str(code), message=message)
        return Envelope(
            id=_new_id("msg"),
            type="session.rejected",
            correlation_id=envelope.id,
            payload=rejected.model_dump(exclude_none=True),
        )


def consume_authenticate(
    state: SessionState, envelope: Envelope
) -> tuple[Envelope, bool]:
    """Process a follow-up ``session.authenticate``.

    Returns ``(response_envelope, accepted)``. v0.1 only uses this for
    re-authentication (``session.refresh``) since the initial open path
    accepts directly when credentials suffice.
    """

    try:
        payload = SessionAuthenticatePayload.model_validate(envelope.payload)
    except Exception as exc:
        rejected = SessionRejectedPayload(
            code=str(ErrorCode.INVALID_ARGUMENT), message=str(exc)
        )
        return (
            Envelope(
                id=_new_id("msg"),
                type="session.rejected",
                correlation_id=envelope.id,
                session_id=state.session_id,
                payload=rejected.model_dump(exclude_none=True),
            ),
            False,
        )

    # v0.1: accept any well-formed authenticate during refresh.
    state.phase = SessionPhase.ACCEPTED
    accepted = SessionAcceptedPayload(
        session_id=state.session_id,
        runtime=state.runtime_identity,
        capabilities=state.capabilities,
        lease=LeaseBlock(expires_at=state.expires_at or _format_iso(_now())),
    )
    del payload
    return (
        Envelope(
            id=_new_id("msg"),
            type="session.accepted",
            correlation_id=envelope.id,
            session_id=state.session_id,
            payload=accepted.model_dump(),
        ),
        True,
    )


__all__ = [
    "HandshakeDriver",
    "HandshakeResult",
    "SessionPhase",
    "SessionState",
    "consume_authenticate",
    "negotiate_capabilities",
]
