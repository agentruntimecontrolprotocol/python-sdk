"""§8.6 job.cancel + §10.3 job.unsubscribe handler coverage."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    InvalidRequestError,
    JobNotFoundError,
    PermissionDeniedError,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._envelope import Envelope
from arcp._messages.execution import JobCancelPayload
from arcp._ulid import new_envelope_id
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


def _make_rt() -> ARCPRuntime:
    return ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )


async def test_cancel_unknown_job_raises_not_found() -> None:
    from arcp._runtime._handlers import handle_cancel

    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    ctx = rt._sessions[welcome.session_id]

    env = Envelope(
        id=new_envelope_id(),
        type="job.cancel",
        session_id=welcome.session_id,
        job_id="nonexistent-job",
        payload=JobCancelPayload(reason="test").model_dump(mode="json"),
    )
    with pytest.raises(JobNotFoundError):
        await handle_cancel(rt, ctx, env)

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_cancel_missing_job_id_raises() -> None:
    from arcp._runtime._handlers import handle_cancel

    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    ctx = rt._sessions[welcome.session_id]

    env = Envelope(
        id=new_envelope_id(),
        type="job.cancel",
        session_id=welcome.session_id,
        job_id=None,  # missing job_id
        payload=JobCancelPayload(reason="test").model_dump(mode="json"),
    )
    with pytest.raises(InvalidRequestError, match="job_id"):
        await handle_cancel(rt, ctx, env)

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_cancel_other_principals_job_raises_permission_denied() -> None:
    from arcp._runtime._handlers import handle_cancel

    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1", "other": "p2"}),
        heartbeat_interval_sec=None,
    )

    long_running_started = asyncio.Event()

    async def slow_agent(input_value, ctx):
        long_running_started.set()
        await asyncio.sleep(10)

    rt.register_agent("slow", slow_agent)

    # Connect as p1 and submit
    server_a, client_a = pair_memory_transports()
    server_b, client_b = pair_memory_transports()
    task_a = asyncio.create_task(rt.accept(server_a))
    task_b = asyncio.create_task(rt.accept(server_b))

    ca = ARCPClient(
        client=ClientInfo(name="a", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    cb = ARCPClient(
        client=ClientInfo(name="b", version="1"),
        token="other",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await ca.connect(client_a)
    welcome_b = await cb.connect(client_b)

    handle = await ca.submit(agent="slow")
    await asyncio.wait_for(long_running_started.wait(), timeout=2.0)

    # p2's ctx tries to cancel p1's job
    ctx_b = rt._sessions[welcome_b.session_id]
    env = Envelope(
        id=new_envelope_id(),
        type="job.cancel",
        session_id=welcome_b.session_id,
        job_id=handle.job_id,
        payload=JobCancelPayload(reason="hostile").model_dump(mode="json"),
    )

    with pytest.raises(PermissionDeniedError):
        await handle_cancel(rt, ctx_b, env)

    for cli in (ca, cb):
        await cli.close()
    for t in (task_a, task_b):
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
    await rt.close()


async def test_cancel_own_job_cancels_task() -> None:
    """Cancelling a running job via client.cancel_job cancels the underlying task."""
    rt = _make_rt()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow_agent(input_value, ctx):
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    rt.register_agent("slow", slow_agent)

    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await client.connect(client_t)

    handle = await client.submit(agent="slow")
    await asyncio.wait_for(started.wait(), timeout=2.0)
    await client.cancel_job(handle.job_id)
    await asyncio.wait_for(cancelled.wait(), timeout=2.0)
    assert cancelled.is_set()

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_unsubscribe_unknown_job_is_noop() -> None:
    """handle_unsubscribe with unknown job_id must silently return."""
    from arcp._messages.execution import JobUnsubscribePayload
    from arcp._runtime._handlers import handle_unsubscribe

    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    ctx = rt._sessions[welcome.session_id]

    env = Envelope(
        id=new_envelope_id(),
        type="job.unsubscribe",
        session_id=welcome.session_id,
        payload=JobUnsubscribePayload(job_id="ghost-job").model_dump(mode="json"),
    )
    # Must not raise
    await handle_unsubscribe(rt, ctx, env)

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()
