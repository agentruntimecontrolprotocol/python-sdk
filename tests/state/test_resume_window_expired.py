"""#66 — resume returns RESUME_WINDOW_EXPIRED for elapsed window / trimmed buffer (§6.3)."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    PermissionDeniedError,
    ResumeWindowExpiredError,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._messages.session import SessionResume
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


def _make_rt() -> ARCPRuntime:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"t": "p1"}),
        heartbeat_interval_sec=None,
    )

    async def echo(input_value, ctx):
        return input_value

    rt.register_agent("echo", echo)
    return rt


async def _submit_then_drop(rt: ARCPRuntime, caps: Capabilities) -> tuple[str, str, int]:
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    try:
        c = ARCPClient(client=ClientInfo(name="c", version="1"), token="t", capabilities=caps)
        w = await c.connect(client_t)
        h = await c.submit(agent="echo", input={"x": 1})
        await asyncio.wait_for(h.done, timeout=2.0)
        latest = c.latest_event_seq
        await client_t.close()  # drop without session.close → resume record kept
        await asyncio.wait_for(accept_task, timeout=2.0)
    finally:
        if not accept_task.done():
            accept_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await accept_task
    return w.session_id, w.resume_token, latest


async def _resume_expect(rt, caps, session_id, resume_token, last_event_seq, exc) -> None:
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    try:
        c = ARCPClient(client=ClientInfo(name="c", version="1"), token="t", capabilities=caps)
        with pytest.raises(exc):
            await c.resume(
                client_t,
                resume=SessionResume(
                    session_id=session_id,
                    resume_token=resume_token,
                    last_event_seq=last_event_seq,
                ),
            )
    finally:
        if not accept_task.done():
            accept_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await accept_task


async def test_resume_after_window_elapsed_returns_window_expired() -> None:
    rt = _make_rt()
    caps = Capabilities(features=rt.capabilities.features)
    session_id, resume_token, _ = await _submit_then_drop(rt, caps)

    # Force the resume record past its window.
    rec = rt._resume_records[session_id]
    rt._resume_records[session_id] = dataclasses.replace(rec, expires_at=0.0)

    await _resume_expect(rt, caps, session_id, resume_token, 0, ResumeWindowExpiredError)
    await rt.close()


async def test_resume_when_buffer_no_longer_covers_returns_window_expired() -> None:
    rt = _make_rt()
    caps = Capabilities(features=rt.capabilities.features)
    session_id, resume_token, latest = await _submit_then_drop(rt, caps)
    assert latest >= 1

    # Simulate acked events being released past last_event_seq=0.
    await rt.event_log.release_through(session_id, latest)

    await _resume_expect(rt, caps, session_id, resume_token, 0, ResumeWindowExpiredError)
    await rt.close()


async def test_resume_unknown_session_still_permission_denied() -> None:
    rt = _make_rt()
    caps = Capabilities(features=rt.capabilities.features)
    await _resume_expect(
        rt, caps, "sess_unknown_xxxxxxxxxxxxxxxxxxxxx", "any", 0, PermissionDeniedError
    )
    await rt.close()
