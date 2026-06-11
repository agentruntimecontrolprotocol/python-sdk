"""Server-side session handshake: validate hello, negotiate features, send welcome."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import datetime as dt
import hmac
from typing import TYPE_CHECKING, Any

from .._envelope import Envelope
from .._errors import InvalidRequestError, PermissionDeniedError
from .._messages.session import (
    Capabilities,
    SessionHelloPayload,
    SessionResume,
    SessionWelcomePayload,
)
from .._time import now_iso_z as _now_iso
from .._ulid import new_envelope_id, new_resume_token
from .._version import intersect_features
from .session import SessionContext, SessionState, make_session_state

if TYPE_CHECKING:
    from .server import ARCPRuntime


async def perform_handshake(runtime: ARCPRuntime, transport: Any) -> SessionContext:
    """Receive hello, authenticate, build session context, send welcome.

    Raises:
        UnauthenticatedError: bearer rejected the supplied token.
        InvalidRequestError: client did not send a valid session.hello first.
        PermissionDeniedError: a `resume` block did not match a live record.
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
    if hello.resume is not None:
        return await _perform_resume(
            runtime, transport, identity, hello.resume, negotiated, welcome_caps
        )
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


async def _perform_resume(  # noqa: PLR0913
    runtime: ARCPRuntime,
    transport: Any,
    identity: Any,
    resume: SessionResume,
    negotiated: tuple[str, ...],
    welcome_caps: Capabilities,
) -> SessionContext:
    """Validate a `hello.resume`, rebuild the session, and replay missed events.

    PLR0913: every parameter is needed (runtime, transport, identity from
    bearer, the resume request, negotiated features, welcome caps). This
    helper exists specifically to keep `perform_handshake` simple.
    """
    record = runtime._pop_resumable(resume.session_id)
    if record is None:
        raise PermissionDeniedError(f"no resumable session for session_id={resume.session_id!r}")
    if not hmac.compare_digest(record.resume_token, resume.resume_token):
        raise PermissionDeniedError("resume_token does not match")
    if record.principal != identity.principal:
        raise PermissionDeniedError("resume principal does not match the original session")
    # Reuse the same session_id (and bump the resume_token so the next
    # resume must use the freshly issued one).
    state = SessionState(
        session_id=record.session_id,
        resume_token=new_resume_token(),
        principal=record.principal,
        negotiated_features=negotiated,
        heartbeat_interval_sec=(
            runtime.heartbeat_interval_sec if "heartbeat" in negotiated else None
        ),
        resume_window_sec=runtime.resume_window_sec,
        accepted_at=dt.datetime.now(dt.UTC),
    )
    send_queue: asyncio.Queue[Envelope | None] = asyncio.Queue()
    ctx = SessionContext(
        transport=transport,
        state=state,
        send_queue=send_queue,
        identity=identity,
    )
    # Continue stamping event_seq past the latest replayed value.
    ctx.set_event_seq(record.last_event_seq)
    runtime._sessions[ctx.session_id] = ctx
    ctx.stamp_and_enqueue(_build_welcome_envelope(runtime, ctx, welcome_caps, negotiated))
    # Replay everything strictly greater than `resume.last_event_seq` so the
    # peer rejoins exactly where it left off.
    async for env_wire in runtime.event_log.read_since_seq(ctx.session_id, resume.last_event_seq):
        ctx.stamp_and_enqueue(Envelope.from_wire(env_wire))
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
