"""§7.6 + §14 — subscriber cannot cancel a job."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import (
    ARCPCancelledError,
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_subscriber_cancel_denied() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"a": "p1", "b": "p2"}),
        heartbeat_interval_sec=None,
        job_authorization_policy=lambda ctx: True,  # cross-principal subscribe ok
    )
    started = asyncio.Event()
    cancel_observed = asyncio.Event()

    async def slow(input_value, ctx):
        started.set()
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            cancel_observed.set()
            raise
        return "done"

    rt.register_agent("slow", slow)

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
        handle = await a.submit(agent="slow")
        await started.wait()
        await b.subscribe(handle.job_id)
        # B's cancel must not affect the job — silently dropped at server.
        await b.cancel_job(handle.job_id)
        await asyncio.sleep(0.2)
        assert not cancel_observed.is_set()
        # A can cancel; cancellation surfaces as job.error/CANCELLED (§7.4).
        await a.cancel_job(handle.job_id)
        with pytest.raises(ARCPCancelledError):
            await handle.done
        assert cancel_observed.is_set()
    finally:
        for cli in (a, b):
            await cli.close()
        for t in (task_a, task_b):
            with contextlib.suppress(Exception):
                await t
        await rt.close()
