"""§10.1 job.subscribe handler — permission checks and history replay."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    JobNotFoundError,
    PermissionDeniedError,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._envelope import Envelope
from arcp._messages.execution import JobSubscribePayload
from arcp._ulid import new_envelope_id
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


def _make_rt(tokens: dict[str, str] | None = None) -> ARCPRuntime:
    return ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier(tokens or {"tok": "p1"}),
        heartbeat_interval_sec=None,
    )


async def test_subscribe_unknown_job_raises_not_found() -> None:
    """handle_subscribe with an unknown job_id raises JobNotFoundError."""
    from arcp._runtime._handlers import handle_subscribe

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
        type="job.subscribe",
        session_id=welcome.session_id,
        payload=JobSubscribePayload(job_id="ghost-job").model_dump(mode="json"),
    )
    with pytest.raises(JobNotFoundError):
        await handle_subscribe(rt, ctx, env)

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_subscribe_other_principals_job_raises_permission_denied() -> None:
    """handle_subscribe with a different principal raises PermissionDeniedError."""
    from arcp._runtime._handlers import handle_subscribe

    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1", "other": "p2"}),
        heartbeat_interval_sec=None,
    )

    started = asyncio.Event()

    async def slow_agent(input_value, ctx):
        started.set()
        await asyncio.sleep(10)

    rt.register_agent("slow", slow_agent)

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
    await asyncio.wait_for(started.wait(), timeout=2.0)

    ctx_b = rt._sessions[welcome_b.session_id]
    env = Envelope(
        id=new_envelope_id(),
        type="job.subscribe",
        session_id=welcome_b.session_id,
        payload=JobSubscribePayload(job_id=handle.job_id).model_dump(mode="json"),
    )
    with pytest.raises(PermissionDeniedError):
        await handle_subscribe(rt, ctx_b, env)

    for cli in (ca, cb):
        await cli.close()
    for t in (task_a, task_b):
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
    await rt.close()


async def test_subscribe_without_history_returns_subscribed() -> None:
    """handle_subscribe without history=True enqueues a job.subscribed envelope."""
    from arcp._runtime._handlers import handle_subscribe

    rt = _make_rt()
    started = asyncio.Event()

    async def slow_agent(input_value, ctx):
        started.set()
        await asyncio.sleep(10)

    rt.register_agent("slow", slow_agent)

    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    handle = await client.submit(agent="slow")
    await asyncio.wait_for(started.wait(), timeout=2.0)

    ctx = rt._sessions[welcome.session_id]

    # Drain existing queue items (welcome, accepted, etc.)
    while not ctx._send_queue.empty():
        ctx._send_queue.get_nowait()

    env = Envelope(
        id=new_envelope_id(),
        type="job.subscribe",
        session_id=welcome.session_id,
        payload=JobSubscribePayload(job_id=handle.job_id, history=False).model_dump(mode="json"),
    )
    await handle_subscribe(rt, ctx, env)

    # There should be a job.subscribed in the queue
    found = False
    try:
        while True:
            item = ctx._send_queue.get_nowait()
            if item is not None and item.type == "job.subscribed":
                found = True
                break
    except asyncio.QueueEmpty:
        pass

    assert found, "expected job.subscribed in queue"

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_subscribe_with_history_replays_events() -> None:
    """handle_subscribe with history=True replays events from the event log."""
    from arcp._runtime._handlers import handle_subscribe

    rt = _make_rt()
    started = asyncio.Event()

    async def slow_agent(input_value, ctx):
        started.set()
        await asyncio.sleep(10)

    rt.register_agent("slow", slow_agent)

    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    handle = await client.submit(agent="slow")
    await asyncio.wait_for(started.wait(), timeout=2.0)

    ctx = rt._sessions[welcome.session_id]

    # Manually inject an event into the event log with a valid ULID id
    await rt.event_log.append(
        welcome.session_id,
        {
            "id": new_envelope_id(),
            "type": "job.event",
            "session_id": welcome.session_id,
            "job_id": handle.job_id,
            "event_seq": 1,
            "payload": {
                "kind": "log",
                "ts": "2024-01-01T00:00:00Z",
                "body": {"level": "info", "message": "hi"},
            },
            "arcp": "1.1",
        },
    )

    # Drain existing queue items
    while not ctx._send_queue.empty():
        ctx._send_queue.get_nowait()

    env = Envelope(
        id=new_envelope_id(),
        type="job.subscribe",
        session_id=welcome.session_id,
        payload=JobSubscribePayload(
            job_id=handle.job_id, history=True, from_event_seq=0
        ).model_dump(mode="json"),
    )
    await handle_subscribe(rt, ctx, env)

    # We should have replayed job.event + job.subscribed
    types_found = set()
    try:
        while True:
            item = ctx._send_queue.get_nowait()
            if item is not None:
                types_found.add(item.type)
    except asyncio.QueueEmpty:
        pass

    assert "job.subscribed" in types_found
    assert "job.event" in types_found

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()
