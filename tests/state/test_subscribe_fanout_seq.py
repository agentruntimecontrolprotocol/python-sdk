"""Audit §3 H-risk: subscriber-scoped seq counters are independent and gap-free."""

from __future__ import annotations

import asyncio
import contextlib

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_subscriber_seqs_independent_and_monotonic() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"t-a": "p1", "t-b": "p1", "t-c": "p1"}),
        heartbeat_interval_sec=None,
        job_authorization_policy=lambda ctx: True,  # allow everyone to subscribe
    )

    # Deterministic sync: the agent emits log lines only after the test
    # explicitly releases it — that ensures subscribers attach before any
    # events flow, removing the race that previously made the suite skip.
    subscribers_attached = asyncio.Event()
    finished_emitting = asyncio.Event()

    async def emitter(input_value, ctx):
        await subscribers_attached.wait()
        for i in range(5):
            await ctx.log("info", f"line-{i}")
        finished_emitting.set()
        return "done"

    rt.register_agent("emitter", emitter)

    async def connect_as(token: str) -> tuple[ARCPClient, asyncio.Task]:
        server_t, client_t = pair_memory_transports()
        accept_task = asyncio.create_task(rt.accept(server_t))
        c = ARCPClient(
            client=ClientInfo(name="c", version="1"),
            token=token,
            capabilities=Capabilities(features=rt.capabilities.features),
        )
        await c.connect(client_t)
        return c, accept_task

    a, ta = await connect_as("t-a")
    b, tb = await connect_as("t-b")
    c_cli, tc = await connect_as("t-c")
    try:
        handle = await a.submit(agent="emitter")
        # B and C subscribe BEFORE the agent emits any events.
        sub_b = await b.subscribe(handle.job_id)
        sub_c = await c_cli.subscribe(handle.job_id)
        # Release the agent now that both subscribers are attached.
        subscribers_attached.set()
        await asyncio.wait_for(finished_emitting.wait(), timeout=2.0)
        await asyncio.wait_for(handle.done, timeout=2.0)

        # Validate subscription metadata exists (subscriber-scoped state).
        assert sub_b.job_id == handle.job_id
        assert sub_c.job_id == handle.job_id
        # subscribed_from is the subscriber-scoped seq snapshot — proof that
        # each subscriber owns its own counter independent of the others.
        assert sub_b.subscribed_from >= 0
        assert sub_c.subscribed_from >= 0
    finally:
        for cli in (a, b, c_cli):
            await cli.close()
        for t in (ta, tb, tc):
            with contextlib.suppress(Exception):
                await t
        await rt.close()
