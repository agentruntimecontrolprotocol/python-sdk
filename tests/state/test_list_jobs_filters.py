"""§5.3 session.list_jobs handler — filter/pagination coverage."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._envelope import Envelope
from arcp._messages.session import ListJobsFilter, SessionListJobsPayload
from arcp._ulid import new_envelope_id
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


def _make_rt() -> ARCPRuntime:
    return ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )


async def _setup(rt: ARCPRuntime):
    """Connect a client and return (client, accept_task, welcome)."""
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    return client, accept_task, welcome


async def test_list_jobs_no_filter_returns_all_own_jobs() -> None:
    """list_jobs with no filter returns all jobs belonging to the principal."""
    from arcp._runtime._handlers import handle_list_jobs

    rt = _make_rt()
    started = asyncio.Event()

    async def slow_agent(input_value, ctx):
        started.set()
        await asyncio.sleep(10)

    rt.register_agent("slow", slow_agent)
    client, accept_task, welcome = await _setup(rt)

    handle = await client.submit(agent="slow")
    await asyncio.wait_for(started.wait(), timeout=2.0)

    ctx = rt._sessions[welcome.session_id]
    # Drain queue
    while not ctx._send_queue.empty():
        ctx._send_queue.get_nowait()

    env = Envelope(
        id=new_envelope_id(),
        type="session.list_jobs",
        session_id=welcome.session_id,
        payload=SessionListJobsPayload().model_dump(mode="json", exclude_none=True),
    )
    await handle_list_jobs(rt, ctx, env)

    found = False
    try:
        while True:
            item = ctx._send_queue.get_nowait()
            if item is not None and item.type == "session.jobs":
                jobs = item.payload.get("jobs", [])
                assert any(j["job_id"] == handle.job_id for j in jobs)
                found = True
                break
    except asyncio.QueueEmpty:
        pass

    assert found, "expected session.jobs in queue"

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_list_jobs_filter_by_agent() -> None:
    """Filter by agent name only returns matching jobs."""
    from arcp._runtime._handlers import handle_list_jobs

    rt = _make_rt()
    started = asyncio.Event()

    async def echo_agent(input_value, ctx):
        pass

    async def slow_agent(input_value, ctx):
        started.set()
        await asyncio.sleep(10)

    rt.register_agent("echo", echo_agent)
    rt.register_agent("slow", slow_agent)

    client, accept_task, welcome = await _setup(rt)

    slow_handle = await client.submit(agent="slow")
    await asyncio.wait_for(started.wait(), timeout=2.0)

    ctx = rt._sessions[welcome.session_id]
    while not ctx._send_queue.empty():
        ctx._send_queue.get_nowait()

    env = Envelope(
        id=new_envelope_id(),
        type="session.list_jobs",
        session_id=welcome.session_id,
        payload=SessionListJobsPayload(
            filter=ListJobsFilter(agent="slow")
        ).model_dump(mode="json", exclude_none=True),
    )
    await handle_list_jobs(rt, ctx, env)

    found = False
    try:
        while True:
            item = ctx._send_queue.get_nowait()
            if item is not None and item.type == "session.jobs":
                jobs = item.payload.get("jobs", [])
                # All returned jobs should be "slow" agent
                assert all(j["agent"] == "slow" for j in jobs)
                assert any(j["job_id"] == slow_handle.job_id for j in jobs)
                found = True
                break
    except asyncio.QueueEmpty:
        pass

    assert found, "expected session.jobs in queue"

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_list_jobs_filter_by_status() -> None:
    """Filter by status 'running' only returns running jobs."""
    from arcp._runtime._handlers import handle_list_jobs

    rt = _make_rt()
    started = asyncio.Event()

    async def slow_agent(input_value, ctx):
        started.set()
        await asyncio.sleep(10)

    rt.register_agent("slow", slow_agent)
    client, accept_task, welcome = await _setup(rt)

    handle = await client.submit(agent="slow")
    await asyncio.wait_for(started.wait(), timeout=2.0)

    ctx = rt._sessions[welcome.session_id]
    while not ctx._send_queue.empty():
        ctx._send_queue.get_nowait()

    env = Envelope(
        id=new_envelope_id(),
        type="session.list_jobs",
        session_id=welcome.session_id,
        payload=SessionListJobsPayload(
            filter=ListJobsFilter(status=["running"])
        ).model_dump(mode="json", exclude_none=True),
    )
    await handle_list_jobs(rt, ctx, env)

    found = False
    try:
        while True:
            item = ctx._send_queue.get_nowait()
            if item is not None and item.type == "session.jobs":
                jobs = item.payload.get("jobs", [])
                assert all(j["status"] == "running" for j in jobs)
                found = True
                break
    except asyncio.QueueEmpty:
        pass

    assert found, "expected session.jobs in queue"

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_list_jobs_filter_by_created_after() -> None:
    """Filter by created_after excludes jobs submitted before the cutoff."""
    from arcp._runtime._handlers import handle_list_jobs

    rt = _make_rt()
    started = asyncio.Event()

    async def slow_agent(input_value, ctx):
        started.set()
        await asyncio.sleep(10)

    rt.register_agent("slow", slow_agent)
    client, accept_task, welcome = await _setup(rt)

    handle = await client.submit(agent="slow")
    await asyncio.wait_for(started.wait(), timeout=2.0)

    ctx = rt._sessions[welcome.session_id]
    while not ctx._send_queue.empty():
        ctx._send_queue.get_nowait()

    # Far-future cutoff → no jobs should match
    future_cutoff = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    env = Envelope(
        id=new_envelope_id(),
        type="session.list_jobs",
        session_id=welcome.session_id,
        payload=SessionListJobsPayload(
            filter=ListJobsFilter(created_after=future_cutoff)
        ).model_dump(mode="json", exclude_none=True),
    )
    await handle_list_jobs(rt, ctx, env)

    found = False
    try:
        while True:
            item = ctx._send_queue.get_nowait()
            if item is not None and item.type == "session.jobs":
                jobs = item.payload.get("jobs", [])
                assert len(jobs) == 0, "future cutoff should exclude all jobs"
                found = True
                break
    except asyncio.QueueEmpty:
        pass

    assert found, "expected session.jobs in queue"

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_list_jobs_cursor_pagination() -> None:
    """Cursor pagination returns next_cursor when more jobs remain."""
    from arcp._runtime._handlers import handle_list_jobs

    rt = _make_rt()
    started1 = asyncio.Event()
    started2 = asyncio.Event()

    async def slow_agent(input_value, ctx):
        if not started1.is_set():
            started1.set()
        else:
            started2.set()
        await asyncio.sleep(10)

    rt.register_agent("slow", slow_agent)
    client, accept_task, welcome = await _setup(rt)

    h1 = await client.submit(agent="slow")
    await asyncio.wait_for(started1.wait(), timeout=2.0)
    h2 = await client.submit(agent="slow")
    await asyncio.wait_for(started2.wait(), timeout=2.0)

    ctx = rt._sessions[welcome.session_id]
    while not ctx._send_queue.empty():
        ctx._send_queue.get_nowait()

    # Request limit=1 → should get one job + next_cursor
    env = Envelope(
        id=new_envelope_id(),
        type="session.list_jobs",
        session_id=welcome.session_id,
        payload=SessionListJobsPayload(limit=1).model_dump(mode="json", exclude_none=True),
    )
    await handle_list_jobs(rt, ctx, env)

    next_cursor = None
    try:
        while True:
            item = ctx._send_queue.get_nowait()
            if item is not None and item.type == "session.jobs":
                jobs = item.payload.get("jobs", [])
                next_cursor = item.payload.get("next_cursor")
                assert len(jobs) == 1
                break
    except asyncio.QueueEmpty:
        pass

    assert next_cursor is not None, "expected next_cursor when 2 jobs but limit=1"

    # Use next_cursor to fetch the second page
    env2 = Envelope(
        id=new_envelope_id(),
        type="session.list_jobs",
        session_id=welcome.session_id,
        payload=SessionListJobsPayload(limit=1, cursor=next_cursor).model_dump(
            mode="json", exclude_none=True
        ),
    )
    await handle_list_jobs(rt, ctx, env2)

    page2_found = False
    try:
        while True:
            item = ctx._send_queue.get_nowait()
            if item is not None and item.type == "session.jobs":
                jobs = item.payload.get("jobs", [])
                assert len(jobs) == 1
                assert item.payload.get("next_cursor") is None, "no more pages"
                page2_found = True
                break
    except asyncio.QueueEmpty:
        pass

    assert page2_found

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()
