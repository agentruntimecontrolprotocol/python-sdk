"""Inbound envelope dispatch for the client read pump."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .._envelope import Envelope
from .._errors import error_from_payload
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
from .._ulid import new_envelope_id

if TYPE_CHECKING:
    from .client import ARCPClient


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


Handler = Callable[[Envelope], Awaitable[None]]


def build_dispatch_table(client: ARCPClient) -> dict[str, Handler]:
    """Construct the verb-to-handler map for an ARCPClient.

    Built once and cached; closed over `client` for state access.
    """
    return {
        "session.ping": lambda e: _on_session_ping(client, e),
        "session.pong": _on_noop,
        "session.error": lambda e: _on_session_error(client, e),
        "session.bye": lambda e: _on_session_bye(client, e),
        "session.jobs": lambda e: _on_session_jobs(client, e),
        "job.subscribed": lambda e: _on_job_subscribed(client, e),
        "job.accepted": lambda e: _on_job_accepted(client, e),
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
    assert client._transport is not None
    await client._transport.send(out.to_wire())


async def _on_session_error(client: ARCPClient, env: Envelope) -> None:
    client._fail_all_handles(error_from_payload(env.payload))


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
    fut = client._pending_accepts.popleft()
    if not fut.done():
        fut.set_result(accepted)


async def _on_job_event(client: ARCPClient, env: Envelope) -> None:
    if env.job_id is None:
        return
    kind = env.payload.get("kind")
    body = env.payload.get("body", {}) or {}
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
    if handle is None:
        return
    if terminal_kind == "result":
        payload = JobResultPayload.model_validate(env.payload)
        handle._resolve_terminal(payload)
    else:
        JobErrorPayload.model_validate(env.payload)  # validate
        handle._reject_terminal(error_from_payload(env.payload))


__all__ = ("Handler", "build_dispatch_table")
