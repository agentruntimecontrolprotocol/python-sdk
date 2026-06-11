"""#81 — surviving jobs deliver to the resumed connection; window events replay (§6.3)."""

from __future__ import annotations

import asyncio
import contextlib

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._envelope import Envelope
from arcp._messages.session import SessionResume
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_jobs_emit_to_resumed_session_and_window_events_replay() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"t": "p1"}),
        heartbeat_interval_sec=None,
    )

    steps = [asyncio.Event() for _ in range(3)]
    emitted = [asyncio.Event() for _ in range(3)]

    async def agent(input_value, ctx):
        for i in range(3):
            await steps[i].wait()
            await ctx.log("info", f"e{i}")
            emitted[i].set()
        return "done"

    rt.register_agent("emitter", agent)
    caps = Capabilities(features=rt.capabilities.features)

    # --- connection 1: submit + one live pre-disconnect event ---------------
    server_a, client_a = pair_memory_transports()
    task_a = asyncio.create_task(rt.accept(server_a))
    a = ARCPClient(client=ClientInfo(name="a", version="1"), token="t", capabilities=caps)
    welcome = await a.connect(client_a)
    handle = await a.submit(agent="emitter")
    job_id = handle.job_id

    steps[0].set()
    await asyncio.wait_for(emitted[0].wait(), timeout=2.0)  # e0 delivered live (seq 1)

    # --- drop the transport mid-run (no session.close) ----------------------
    await client_a.close()
    await asyncio.wait_for(task_a, timeout=2.0)

    # e1 is emitted while there is NO live connection (disconnect window).
    steps[1].set()
    await asyncio.wait_for(emitted[1].wait(), timeout=2.0)

    # The window event must have been appended to the event log for replay.
    logged = [
        e
        async for e in rt.event_log.read_since_seq(welcome.session_id, 1)
        if e.get("job_id") == job_id
    ]
    assert any(
        e["payload"].get("body", {}).get("message") == "e1" for e in logged
    ), f"window event e1 not persisted: {logged}"

    # --- connection 2: resume ----------------------------------------------
    server_b, client_b = pair_memory_transports()
    task_b = asyncio.create_task(rt.accept(server_b))
    b = ARCPClient(client=ClientInfo(name="b", version="1"), token="t", capabilities=caps)
    await b.resume(
        client_b,
        resume=SessionResume(
            session_id=welcome.session_id,
            resume_token=welcome.resume_token,
            last_event_seq=1,  # replay everything after the live pre-drop event
        ),
    )

    # Observe post-resume traffic for the job.
    seen: list[tuple[str, int | None, str | None]] = []
    orig = b._dispatch

    async def spy(env: Envelope) -> None:
        if env.job_id == job_id:
            msg = env.payload.get("body", {}).get("message") if env.type == "job.event" else None
            seen.append((env.type, env.event_seq, msg))
        await orig(env)

    b._dispatch = spy  # type: ignore[assignment,method-assign]

    try:
        # e2 is emitted AFTER resume → must reach the resumed transport live.
        steps[2].set()
        await asyncio.wait_for(emitted[2].wait(), timeout=2.0)
        await asyncio.sleep(0.1)  # let the post-resume events drain to B

        kinds = [t for t, _, _ in seen]
        msgs = [m for _, _, m in seen if m is not None]
        assert "e2" in msgs, f"post-resume live event not delivered: {seen}"
        assert "job.result" in kinds, f"terminal not delivered to resumed session: {seen}"

        # The seqs B observes are strictly increasing (no collision/gap).
        seqs = [s for _, s, _ in seen if s is not None]
        assert seqs == sorted(seqs) and len(seqs) == len(set(seqs)), seqs
    finally:
        for c in (a, b):
            with contextlib.suppress(Exception):
                await c.close()
        for t in (task_a, task_b):
            if not t.done():
                t.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        await rt.close()
