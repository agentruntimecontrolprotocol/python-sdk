"""Inbound envelope dispatch for the client read pump."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, cast

from .._envelope import Envelope
from .._errors import InternalError, error_from_payload
from .._messages.execution import (
    JobAcceptedPayload,
    JobErrorPayload,
    JobResultPayload,
    JobSubscribedPayload,
)
from .._messages.session import (
    SessionJobsPayload,
    SessionPingPayload,
    SessionPongPayload,
)
from .._time import now_iso_z as _now_iso
from .._ulid import new_envelope_id
from .handles import JobHandle

if TYPE_CHECKING:
    from .client import ARCPClient


Handler = Callable[[Envelope], Awaitable[None]]


def build_dispatch_table(client: ARCPClient) -> dict[str, Handler]:
    """Construct the verb-to-handler map for an ARCPClient.

    Built once and cached; closed over `client` for state access.
    """
    return {
        "session.ping": lambda e: _on_session_ping(client, e),
        "session.pong": _on_noop,
        "session.error": lambda e: _on_session_error(client, e),
        # §6.7 graceful close: `session.closed` is the runtime's ack; legacy
        # peers may still send `session.bye`.
        "session.closed": lambda e: _on_session_bye(client, e),
        "session.bye": lambda e: _on_session_bye(client, e),
        "session.jobs": lambda e: _on_session_jobs(client, e),
        "job.subscribed": lambda e: _on_job_subscribed(client, e),
        "job.accepted": lambda e: _on_job_accepted(client, e),
        # §7.4 cancel ack; the terminal job.error(CANCELLED) resolves the handle.
        "job.cancelled": _on_noop,
        "job.event": lambda e: _on_job_event(client, e),
        "job.result": lambda e: _on_job_terminal(client, e, terminal_kind="result"),
        "job.error": lambda e: _on_job_terminal(client, e, terminal_kind="error"),
    }


async def _on_noop(_env: Envelope) -> None:
    return


async def _on_session_ping(client: ARCPClient, env: Envelope) -> None:
    ping = SessionPingPayload.model_validate(env.payload)
    pong = SessionPongPayload(ping_nonce=ping.nonce, received_at=_now_iso())
    out = Envelope(
        id=new_envelope_id(),
        type="session.pong",
        session_id=client._session_id,
        payload=pong.model_dump(mode="json"),
    )
    if client._transport is None:
        raise InternalError("client received session.ping before transport was attached")
    await client._transport.send(out.to_wire())


async def _on_session_error(client: ARCPClient, env: Envelope) -> None:
    err = error_from_payload(env.payload)
    details = env.payload.get("details")
    request_id = (
        cast("dict[str, Any]", details).get("request_id") if isinstance(details, dict) else None
    )
    # A per-request dispatch failure (e.g. an unknown agent on one submit)
    # carries the originating request_id; fail only that request so unrelated
    # in-flight job handles keep running (#71). Errors without a request_id
    # are treated as session-fatal and fail everything.
    if isinstance(request_id, str) and client._fail_request(request_id, err):
        return
    client._fail_all_handles(err)


async def _on_session_bye(client: ARCPClient, _env: Envelope) -> None:
    await client.close(reason="peer.bye")


async def _on_session_jobs(client: ARCPClient, env: Envelope) -> None:
    payload = SessionJobsPayload.model_validate(env.payload)
    client._pending.resolve(payload.request_id, payload)


async def _on_job_subscribed(client: ARCPClient, env: Envelope) -> None:
    payload = JobSubscribedPayload.model_validate(env.payload)
    client._pending.resolve(payload.request_id, payload)


async def _on_job_accepted(client: ARCPClient, env: Envelope) -> None:
    if not client._pending_accepts:
        return
    accepted = JobAcceptedPayload.model_validate(env.payload)
    fut: asyncio.Future[tuple[JobAcceptedPayload, JobHandle]] | None = None
    if accepted.request_id is not None:
        # New runtimes echo the submit envelope id as request_id; correlate
        # directly so concurrent or out-of-order accepts resolve correctly.
        fut = client._pending_accepts.pop(accepted.request_id, None)
    if fut is None:
        # Legacy runtimes omit request_id: fall back to FIFO matching, which
        # is correct for serialized submits.
        oldest_key = next(iter(client._pending_accepts))
        fut = client._pending_accepts.pop(oldest_key)
    # Create and register the handle synchronously *before* resolving the
    # submit future. If a terminal envelope follows immediately (e.g. an
    # idempotent replay of a completed job), the dispatcher pops the same
    # handle out of `_handles` and resolves it. The handle is also returned
    # in the future result so the awaiting `submit()` uses *this* handle
    # (even if it has already been popped on terminal by the time submit
    # resumes).
    handle = JobHandle(job_id=accepted.job_id, accepted=accepted)
    client._handles[accepted.job_id] = handle
    if not fut.done():
        fut.set_result((accepted, handle))


async def _on_job_event(client: ARCPClient, env: Envelope) -> None:
    if env.job_id is None:
        return
    kind = env.payload.get("kind")
    body: dict[str, Any] = env.payload.get("body", {}) or {}
    handle = client._handles.get(env.job_id)
    if handle is None:
        return
    if kind == "result_chunk":
        handle._push_chunk(body)
    else:
        handle._push_event({"kind": kind, "body": body, "ts": env.payload.get("ts")})


async def _on_job_terminal(client: ARCPClient, env: Envelope, *, terminal_kind: str) -> None:
    if env.job_id is None:
        return
    handle = client._handles.pop(env.job_id, None)
    # Terminal events end any active subscription for this job; the client
    # only needs to call `unsubscribe()` to opt out *before* completion.
    client._subscriptions.pop(env.job_id, None)
    if handle is None:
        return
    if terminal_kind == "result":
        payload = JobResultPayload.model_validate(env.payload)
        handle._resolve_terminal(payload)
    else:
        JobErrorPayload.model_validate(env.payload)  # validate
        handle._reject_terminal(error_from_payload(env.payload))


__all__ = ("Handler", "build_dispatch_table")
