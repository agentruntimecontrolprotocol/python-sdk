"""§6.2 — resume token rotates between sessions + resume replay (#41)."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._errors import PermissionDeniedError
from arcp._messages.session import SessionResume
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_resume_token_rotates_across_connections() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"t": "p1"}),
        heartbeat_interval_sec=None,
    )
    tokens: list[str] = []
    accept_tasks: list[asyncio.Task] = []
    for _ in range(2):
        server_t, client_t = pair_memory_transports()
        accept_tasks.append(asyncio.create_task(rt.accept(server_t)))
        c = ARCPClient(
            client=ClientInfo(name="c", version="1"),
            token="t",
            capabilities=Capabilities(features=rt.capabilities.features),
        )
        w = await c.connect(client_t)
        tokens.append(w.resume_token)
        await c.close()
    for t in accept_tasks:
        if not t.done():
            t.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
    assert tokens[0] != tokens[1]
    await rt.close()


async def _run_one_submit(
    rt: ARCPRuntime, capabilities: Capabilities
) -> tuple[str, str, int]:
    """Connect, submit one job, wait for result, drop transport. Return (session_id, resume_token, latest_seq)."""
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    try:
        c = ARCPClient(
            client=ClientInfo(name="c", version="1"),
            token="t",
            capabilities=capabilities,
        )
        w = await c.connect(client_t)
        h = await c.submit(agent="echo", input={"x": 1})
        await asyncio.wait_for(h.done, timeout=2.0)
        latest = c.latest_event_seq
        # Drop the transport WITHOUT sending session.bye so the server keeps
        # a resume record for us.
        await client_t.close()
        # Wait for the server-side session loop to exit and stash a record.
        await asyncio.wait_for(accept_task, timeout=2.0)
    finally:
        if not accept_task.done():
            accept_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await accept_task
    return w.session_id, w.resume_token, latest


async def test_resume_replay_events_after_disconnect() -> None:
    """A resumed session replays log envelopes the peer never acked."""
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"t": "p1"}),
        heartbeat_interval_sec=None,
    )

    async def echo(input_value: dict, ctx) -> dict:
        return input_value

    rt.register_agent("echo", echo)
    caps = Capabilities(features=rt.capabilities.features)

    session_id, resume_token, latest_seq = await _run_one_submit(rt, caps)
    assert latest_seq >= 1, "expected at least one event_seq-bearing envelope"

    # Resume: replay every event past 0 so we observe the replay.
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    try:
        c = ARCPClient(
            client=ClientInfo(name="c", version="1"),
            token="t",
            capabilities=caps,
        )
        welcome = await c.resume(
            client_t,
            resume=SessionResume(
                session_id=session_id, resume_token=resume_token, last_event_seq=0
            ),
        )
        # Resume reuses the same session_id.
        assert welcome.session_id == session_id
        # Resume rotates the resume_token.
        assert welcome.resume_token != resume_token
        # Drain replayed envelopes from the read pump for a brief window.
        await asyncio.sleep(0.05)
        assert c.latest_event_seq >= latest_seq, (
            f"expected replayed seq>={latest_seq}, got {c.latest_event_seq}"
        )
        await c.close()
    finally:
        if not accept_task.done():
            accept_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await accept_task
    await rt.close()


async def test_resume_rejects_wrong_token() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"t": "p1"}),
        heartbeat_interval_sec=None,
    )

    async def echo(input_value: dict, ctx) -> dict:
        return input_value

    rt.register_agent("echo", echo)
    caps = Capabilities(features=rt.capabilities.features)
    session_id, _resume_token, _ = await _run_one_submit(rt, caps)

    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    try:
        c = ARCPClient(
            client=ClientInfo(name="c", version="1"),
            token="t",
            capabilities=caps,
        )
        with pytest.raises(PermissionDeniedError):
            await c.resume(
                client_t,
                resume=SessionResume(
                    session_id=session_id,
                    resume_token="wrong-token",
                    last_event_seq=0,
                ),
            )
    finally:
        if not accept_task.done():
            accept_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await accept_task
    await rt.close()


async def test_resume_rejects_unknown_session_id() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"t": "p1"}),
        heartbeat_interval_sec=None,
    )
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    try:
        c = ARCPClient(
            client=ClientInfo(name="c", version="1"),
            token="t",
            capabilities=Capabilities(features=rt.capabilities.features),
        )
        with pytest.raises(PermissionDeniedError):
            await c.resume(
                client_t,
                resume=SessionResume(
                    session_id="sess_unknown_session_id_xxxxxxxxx",
                    resume_token="any",
                    last_event_seq=0,
                ),
            )
    finally:
        if not accept_task.done():
            accept_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await accept_task
    await rt.close()
