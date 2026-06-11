"""#89 — per-session event-log memory is reclaimed after the resume window."""

from __future__ import annotations

import asyncio
import contextlib

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._store.eventlog import InMemoryEventLog
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def _drain(event_log: InMemoryEventLog, session_id: str) -> list[dict]:
    return [e async for e in event_log.read_since_seq(session_id, 0)]


async def test_event_log_dropped_when_resume_disabled() -> None:
    log = InMemoryEventLog()
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
        resume_window_sec=0,  # resume disabled => log unreachable after end
        event_log=log,
    )

    async def echo(input_value, ctx):
        await ctx.log("info", "hi")
        return input_value

    rt.register_agent("echo", echo)

    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    handle = await client.submit(agent="echo", input={"x": 1})
    await asyncio.wait_for(handle.done, timeout=2.0)
    session_id = welcome.session_id
    assert len(await _drain(log, session_id)) >= 1, "expected buffered events"

    # End the session; with no resume window its log must be released.
    await client.close()
    await asyncio.wait_for(accept_task, timeout=2.0)

    assert await _drain(log, session_id) == []
    await rt.close()


async def test_reclaim_drops_logs_for_expired_resume_records() -> None:
    log = InMemoryEventLog()
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
        resume_window_sec=600,
        event_log=log,
    )

    async def echo(input_value, ctx):
        await ctx.log("info", "hi")
        return input_value

    rt.register_agent("echo", echo)

    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    handle = await client.submit(agent="echo", input={"x": 1})
    await asyncio.wait_for(handle.done, timeout=2.0)
    session_id = welcome.session_id

    # Drop the transport WITHOUT session.close so a resume record is kept.
    await client_t.close()
    await asyncio.wait_for(accept_task, timeout=2.0)
    assert session_id in rt._resume_records
    assert len(await _drain(log, session_id)) >= 1

    # Force the record past its window, then reclaim.
    import dataclasses

    rec = rt._resume_records[session_id]
    rt._resume_records[session_id] = dataclasses.replace(rec, expires_at=0.0)
    await rt._reclaim_expired_event_logs()

    assert session_id not in rt._resume_records
    assert await _drain(log, session_id) == []

    with contextlib.suppress(Exception):
        await client.close()
    await rt.close()
