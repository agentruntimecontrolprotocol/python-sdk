"""Server-side session handshake: validate hello, negotiate features, send welcome."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .._envelope import Envelope
from .._errors import InvalidRequestError
from .._messages.session import (
    Capabilities,
    SessionHelloPayload,
    SessionWelcomePayload,
)
from .._ulid import new_envelope_id
from .._version import intersect_features
from .session import SessionContext, make_session_state

if TYPE_CHECKING:
    from .server import ARCPRuntime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


async def perform_handshake(runtime: ARCPRuntime, transport: Any) -> SessionContext:
    """Receive hello, authenticate, build session context, send welcome.

    Raises:
        UnauthenticatedError: bearer rejected the supplied token.
        InvalidRequestError: client did not send a valid session.hello first.
    """
    raw = await transport.recv()
    env = Envelope.from_wire(raw)
    if env.type != "session.hello":
        raise InvalidRequestError(f"expected session.hello as first envelope, got {env.type!r}")
    hello = SessionHelloPayload.model_validate(env.payload)
    identity = await runtime.bearer.verify(hello.auth.token)
    negotiated = intersect_features(
        tuple(runtime.capabilities.features),
        tuple(hello.capabilities.features),
    )
    welcome_caps = _build_welcome_caps(runtime, negotiated)
    state = make_session_state(
        principal=identity.principal,
        negotiated_features=negotiated,
        heartbeat_interval_sec=(
            runtime.heartbeat_interval_sec if "heartbeat" in negotiated else None
        ),
        resume_window_sec=runtime.resume_window_sec,
    )
    send_queue: asyncio.Queue[Envelope | None] = asyncio.Queue()
    ctx = SessionContext(
        transport=transport,
        state=state,
        send_queue=send_queue,
        identity=identity,
    )
    runtime._sessions[ctx.session_id] = ctx
    ctx.stamp_and_enqueue(_build_welcome_envelope(runtime, ctx, welcome_caps, negotiated))
    return ctx


def _build_welcome_caps(runtime: ARCPRuntime, negotiated: tuple[str, ...]) -> Capabilities:
    return Capabilities(
        encodings=tuple(runtime.capabilities.encodings),
        features=tuple(runtime.capabilities.features),
        agents=(
            runtime.agent_inventory()
            if "agent_versions" in negotiated
            else tuple(reg.name for reg in runtime._agents.values())
        ),
    )


def _build_welcome_envelope(
    runtime: ARCPRuntime,
    ctx: SessionContext,
    welcome_caps: Capabilities,
    negotiated: tuple[str, ...],
) -> Envelope:
    welcome = SessionWelcomePayload(
        runtime=runtime.runtime_info,
        session_id=ctx.session_id,
        resume_token=ctx.state.resume_token,
        resume_window_sec=runtime.resume_window_sec,
        heartbeat_interval_sec=(
            runtime.heartbeat_interval_sec if "heartbeat" in negotiated else None
        ),
        capabilities=welcome_caps,
        accepted_at=_now_iso(),
    )
    return Envelope(
        id=new_envelope_id(),
        type="session.welcome",
        session_id=ctx.session_id,
        payload=welcome.model_dump(mode="json", exclude_none=True),
    )


__all__ = ("perform_handshake",)
