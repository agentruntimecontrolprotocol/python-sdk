"""#65 — cancellation emits job.cancelled ack then job.error/CANCELLED (§7.4)."""

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


async def test_cancel_emits_ack_then_job_error_cancelled() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )
    started = asyncio.Event()

    async def slow_agent(input_value, ctx):
        started.set()
        await asyncio.sleep(30)

    rt.register_agent("slow", slow_agent)

    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await client.connect(client_t)

    seen: list[str] = []
    orig_dispatch = client._dispatch

    async def spy(env):  # type: ignore[no-untyped-def]
        seen.append(env.type)
        await orig_dispatch(env)

    client._dispatch = spy  # type: ignore[assignment,method-assign]

    try:
        handle = await client.submit(agent="slow")
        await asyncio.wait_for(started.wait(), timeout=2.0)
        await client.cancel_job(handle.job_id)

        with pytest.raises(ARCPCancelledError) as excinfo:
            await asyncio.wait_for(handle.done, timeout=2.0)
        assert excinfo.value.code == "CANCELLED"

        # The ack precedes the terminal error.
        assert "job.cancelled" in seen, seen
        assert "job.error" in seen, seen
        assert seen.index("job.cancelled") < seen.index("job.error")
    finally:
        with contextlib.suppress(Exception):
            await client.close()
        accept_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await accept_task
        await rt.close()
