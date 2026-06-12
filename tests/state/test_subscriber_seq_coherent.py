"""#83 — a subscriber's merged stream uses one monotonic, gap-free seq space (§8.3)."""

from __future__ import annotations

import asyncio
import contextlib
from itertools import pairwise

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._envelope import Envelope
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier

_SEQ_TYPES = {"job.event", "job.result", "job.error"}


def _spy_seqs(client: ARCPClient, out: list[int]) -> None:
    orig = client._dispatch

    async def spy(env: Envelope) -> None:
        if env.type in _SEQ_TYPES and env.event_seq is not None:
            out.append(env.event_seq)
        await orig(env)

    client._dispatch = spy  # type: ignore[assignment,method-assign]


def _assert_monotonic_gapfree(seqs: list[int]) -> None:
    assert seqs == sorted(seqs), f"not monotonic: {seqs}"
    assert len(seqs) == len(set(seqs)), f"duplicate seq: {seqs}"
    # gap-free: consecutive values differ by exactly 1.
    for a, b in pairwise(seqs):
        assert b == a + 1, f"gap in seq stream: {seqs}"


async def _connect(rt: ARCPRuntime, token: str) -> tuple[ARCPClient, asyncio.Task]:
    server_t, client_t = pair_memory_transports()
    task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token=token,
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await client.connect(client_t)
    return client, task


async def test_subscriber_to_two_jobs_has_coherent_seq_space() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"a": "p1", "b": "p1"}),
        heartbeat_interval_sec=None,
        job_authorization_policy=lambda ctx: True,
    )
    gate = asyncio.Event()
    done = asyncio.Event()
    finished = 0

    async def emitter(input_value, ctx):
        nonlocal finished
        await gate.wait()
        for i in range(4):
            await ctx.log("info", f"line-{i}")
        finished += 1
        if finished == 2:
            done.set()
        return "ok"

    rt.register_agent("emitter", emitter)

    a, ta = await _connect(rt, "a")
    b, tb = await _connect(rt, "b")
    seqs: list[int] = []
    _spy_seqs(b, seqs)
    try:
        h1 = await a.submit(agent="emitter")
        h2 = await a.submit(agent="emitter")
        await b.subscribe(h1.job_id)
        await b.subscribe(h2.job_id)
        gate.set()
        await asyncio.wait_for(done.wait(), timeout=3.0)
        await asyncio.wait_for(h1.done, timeout=3.0)
        await asyncio.wait_for(h2.done, timeout=3.0)
        await asyncio.sleep(0.1)  # let fan-out drain to B

        # B saw events from both jobs plus both terminals on one coherent space.
        assert len(seqs) >= 8
        _assert_monotonic_gapfree(seqs)
    finally:
        for c in (a, b):
            with contextlib.suppress(Exception):
                await c.close()
        for t in (ta, tb):
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        await rt.close()


async def test_subscriber_own_job_and_fanout_share_seq_space() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"a": "p1", "b": "p1"}),
        heartbeat_interval_sec=None,
        job_authorization_policy=lambda ctx: True,
    )
    gate = asyncio.Event()

    async def emitter(input_value, ctx):
        await gate.wait()
        for i in range(3):
            await ctx.log("info", f"x-{i}")
        return "ok"

    rt.register_agent("emitter", emitter)

    a, ta = await _connect(rt, "a")
    b, tb = await _connect(rt, "b")
    seqs: list[int] = []
    _spy_seqs(b, seqs)
    try:
        # B subscribes to A's job AND submits its own job; both flow on B's
        # single session seq space.
        h_a = await a.submit(agent="emitter")
        await b.subscribe(h_a.job_id)
        h_b = await b.submit(agent="emitter")
        gate.set()
        await asyncio.wait_for(h_a.done, timeout=3.0)
        await asyncio.wait_for(h_b.done, timeout=3.0)
        await asyncio.sleep(0.1)

        assert len(seqs) >= 8
        _assert_monotonic_gapfree(seqs)
    finally:
        for c in (a, b):
            with contextlib.suppress(Exception):
                await c.close()
        for t in (ta, tb):
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        await rt.close()
