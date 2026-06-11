"""#70 — max_runtime_sec expiry yields a terminal job.error/TIMEOUT (§12, §7.3)."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import (
    ARCPTimeoutError,
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_timeout_emits_job_error_with_timeout_code() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )

    async def slow_agent(input_value, ctx):
        await asyncio.sleep(30)
        return "never"

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
        handle = await client.submit(agent="slow", max_runtime_sec=1)
        with pytest.raises(ARCPTimeoutError) as excinfo:
            await asyncio.wait_for(handle.done, timeout=5.0)
        assert excinfo.value.code == "TIMEOUT"
        assert excinfo.value.retryable is False
    finally:
        with contextlib.suppress(Exception):
            await client.close()
        accept_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await accept_task
        await rt.close()
