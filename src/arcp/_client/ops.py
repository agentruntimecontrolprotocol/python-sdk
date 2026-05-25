"""Outbound client verbs: submit, cancel, list_jobs, subscribe, unsubscribe, ack."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .._envelope import Envelope
from .._errors import ARCPError, InternalError, InvalidRequestError
from .._messages.execution import (
    JobAcceptedPayload,
    JobCancelPayload,
    JobSubmitPayload,
    JobSubscribedPayload,
    JobSubscribePayload,
    JobUnsubscribePayload,
    Lease,
    LeaseConstraints,
)
from .._messages.session import (
    ListJobsFilter,
    SessionAckPayload,
    SessionJobsPayload,
    SessionListJobsPayload,
)
from .._transport.base import Transport
from .._ulid import new_envelope_id
from .handles import JobHandle, JobSubscription

if TYPE_CHECKING:
    from .client import ARCPClient


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _require_transport(client: ARCPClient) -> Transport:
    """Return the connected transport or raise `InternalError` if absent.

    Uses an explicit raise rather than `assert` so the check survives
    `python -O` / `PYTHONOPTIMIZE=1`. Doubles as a pyright type narrower.
    """
    if client._transport is None:
        raise InternalError("transport not connected; call `await client.connect(...)` first")
    return client._transport


async def submit_job(  # noqa: PLR0913
    client: ARCPClient,
    *,
    agent: str,
    input: Any = None,
    lease_request: Lease | None = None,
    lease_constraints: LeaseConstraints | None = None,
    idempotency_key: str | None = None,
    max_runtime_sec: int | None = None,
    trace_id: str | None = None,
    parent_job_id: str | None = None,
) -> JobHandle:
    # PLR0913: every arg is an optional protocol-payload field. Bundling
    # them in a dataclass for one operation reduces ergonomics.
    transport = _require_transport(client)
    submit = JobSubmitPayload(
        agent=agent,
        input=input,
        lease_request=lease_request or {},
        lease_constraints=lease_constraints,
        idempotency_key=idempotency_key,
        max_runtime_sec=max_runtime_sec,
        parent_job_id=parent_job_id,
    )
    env_id = new_envelope_id()
    env = Envelope(
        id=env_id,
        type="job.submit",
        session_id=client._session_id,
        trace_id=trace_id,
        payload=submit.model_dump(mode="json", exclude_none=True),
    )
    accept_fut: asyncio.Future[tuple[JobAcceptedPayload, JobHandle]] = (
        asyncio.get_running_loop().create_future()
    )
    client._pending_accepts[env_id] = accept_fut
    await transport.send(env.to_wire())
    try:
        _, handle = await asyncio.wait_for(accept_fut, timeout=client.handshake_timeout_sec)
    except (TimeoutError, ARCPError):
        client._pending_accepts.pop(env_id, None)
        raise
    return handle


async def cancel_job(client: ARCPClient, job_id: str, *, reason: str = "client.cancel") -> None:
    transport = _require_transport(client)
    payload = JobCancelPayload(reason=reason)
    env = Envelope(
        id=new_envelope_id(),
        type="job.cancel",
        session_id=client._session_id,
        job_id=job_id,
        payload=payload.model_dump(mode="json", exclude_none=True),
    )
    await transport.send(env.to_wire())


async def list_jobs(
    client: ARCPClient,
    *,
    filter: ListJobsFilter | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> SessionJobsPayload:
    if not client.has_feature("list_jobs"):
        raise InvalidRequestError("feature 'list_jobs' not negotiated")
    transport = _require_transport(client)
    payload = SessionListJobsPayload(filter=filter, limit=limit, cursor=cursor)
    env_id = new_envelope_id()
    fut = client._pending.register(env_id)
    env = Envelope(
        id=env_id,
        type="session.list_jobs",
        session_id=client._session_id,
        payload=payload.model_dump(mode="json", exclude_none=True),
    )
    await transport.send(env.to_wire())
    result = await fut
    if not isinstance(result, SessionJobsPayload):
        raise InternalError(f"expected SessionJobsPayload, got {type(result).__name__}")
    return result


async def subscribe(
    client: ARCPClient,
    job_id: str,
    *,
    history: bool = False,
    from_event_seq: int | None = None,
) -> JobSubscription:
    if not client.has_feature("subscribe"):
        raise InvalidRequestError("feature 'subscribe' not negotiated")
    transport = _require_transport(client)
    payload = JobSubscribePayload(job_id=job_id, history=history, from_event_seq=from_event_seq)
    env_id = new_envelope_id()
    fut = client._pending.register(env_id)
    env = Envelope(
        id=env_id,
        type="job.subscribe",
        session_id=client._session_id,
        job_id=job_id,
        payload=payload.model_dump(mode="json", exclude_none=True),
    )
    await transport.send(env.to_wire())
    subscribed: JobSubscribedPayload = await fut
    accepted = JobAcceptedPayload(
        job_id=subscribed.job_id,
        agent=subscribed.agent,
        accepted_at=_now_iso(),
        lease=subscribed.lease,
        parent_job_id=subscribed.parent_job_id,
        trace_id=subscribed.trace_id,
    )
    handle = JobHandle(job_id=subscribed.job_id, accepted=accepted)
    client._handles[subscribed.job_id] = handle
    sub = JobSubscription(
        job_id=subscribed.job_id,
        request_id=subscribed.request_id,
        subscribed_from=subscribed.subscribed_from,
        replayed=subscribed.replayed,
        handle=handle,
    )
    client._subscriptions[subscribed.job_id] = sub
    return sub


async def unsubscribe(client: ARCPClient, job_id: str) -> None:
    if not client.has_feature("subscribe"):
        return
    transport = _require_transport(client)
    payload = JobUnsubscribePayload(job_id=job_id)
    env = Envelope(
        id=new_envelope_id(),
        type="job.unsubscribe",
        session_id=client._session_id,
        payload=payload.model_dump(mode="json"),
    )
    await transport.send(env.to_wire())
    client._subscriptions.pop(job_id, None)


async def ack(client: ARCPClient, last_processed_seq: int) -> None:
    if not client.has_feature("ack"):
        return
    transport = _require_transport(client)
    payload = SessionAckPayload(last_processed_seq=last_processed_seq)
    env = Envelope(
        id=new_envelope_id(),
        type="session.ack",
        session_id=client._session_id,
        payload=payload.model_dump(mode="json"),
    )
    await transport.send(env.to_wire())


async def close_session(client: ARCPClient, *, reason: str = "client.close") -> None:
    from .._messages.session import SessionByePayload
    from .._transport.base import TransportClosed

    if client._closed:
        return
    client._closed = True
    if client._transport is not None and not client._transport.is_closed:
        try:
            bye = SessionByePayload(reason=reason)
            env = Envelope(
                id=new_envelope_id(),
                type="session.bye",
                session_id=client._session_id,
                payload=bye.model_dump(mode="json", exclude_none=True),
            )
            await client._transport.send(env.to_wire())
        except TransportClosed:
            pass
        await client._transport.close()
    if client._read_task is not None and not client._read_task.done():
        client._read_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await client._read_task
    if client._auto_ack_task is not None and not client._auto_ack_task.done():
        client._auto_ack_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await client._auto_ack_task
    client._fail_all_handles(TransportClosed("client closed"))


__all__ = (
    "ack",
    "cancel_job",
    "close_session",
    "list_jobs",
    "submit_job",
    "subscribe",
    "unsubscribe",
)
