"""§6.6 + §14 — cross-principal default policy hides jobs."""

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


async def test_cross_principal_jobs_hidden() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"a": "p1", "b": "p2"}),
        heartbeat_interval_sec=None,
    )

    async def agent(input_value, ctx):
        await asyncio.sleep(0.05)
        return "ok"

    rt.register_agent("a-agent", agent)

    server_a, client_a = pair_memory_transports()
    server_b, client_b = pair_memory_transports()
    task_a = asyncio.create_task(rt.accept(server_a))
    task_b = asyncio.create_task(rt.accept(server_b))

    a = ARCPClient(
        client=ClientInfo(name="a", version="1"),
        token="a",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    b = ARCPClient(
        client=ClientInfo(name="b", version="1"),
        token="b",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await a.connect(client_a)
    await b.connect(client_b)
    try:
        await a.submit(agent="a-agent")
        await asyncio.sleep(0.1)
        jobs = await b.list_jobs()
        # P2 must not see P1's jobs.
        assert all(j.job_id != "" for j in jobs.jobs)
        assert len(jobs.jobs) == 0
    finally:
        for cli in (a, b):
            await cli.close()
        for t in (task_a, task_b):
            if not t.done():
                t.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        await rt.close()
