"""#71 — a per-request session.error fails only the offending request."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import (
    AgentNotAvailableError,
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_bad_submit_does_not_fail_unrelated_running_job() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_agent(input_value, ctx):
        started.set()
        await release.wait()
        return "ok"

    rt.register_agent("slow", slow_agent)

    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await client.connect(client_t)
    try:
        handle = await client.submit(agent="slow")
        await asyncio.wait_for(started.wait(), timeout=2.0)

        # A bad submit (unknown agent) raises only for that submit.
        with pytest.raises(AgentNotAvailableError):
            await client.submit(agent="does-not-exist")

        # The running job's handle is untouched.
        assert not handle._terminal.done()  # pyright: ignore[reportPrivateUsage]

        # And it still resolves normally once released.
        release.set()
        result = await asyncio.wait_for(handle.done, timeout=2.0)
        assert result.result == "ok"
    finally:
        with contextlib.suppress(Exception):
            await client.close()
        accept_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await accept_task
        await rt.close()
