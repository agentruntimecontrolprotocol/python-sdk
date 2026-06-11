"""§7.3 — job lifecycle transitions."""

from __future__ import annotations

import asyncio

import pytest

from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime


async def test_success_path(runtime: ARCPRuntime, client: ARCPClient) -> None:
    async def agent(input_value, ctx):
        return {"echoed": input_value}

    runtime.register_agent("echo", agent)
    handle = await client.submit(agent="echo", input="hello")
    result = await handle.done
    assert result.final_status == "success"
    assert result.result == {"echoed": "hello"}


async def test_error_path(runtime: ARCPRuntime, client: ARCPClient) -> None:
    async def boom(input_value, ctx):
        raise RuntimeError("kaboom")

    runtime.register_agent("boom", boom)
    handle = await client.submit(agent="boom")
    with pytest.raises(Exception):
        await handle.done


async def test_cancel_running(runtime: ARCPRuntime, client: ARCPClient) -> None:
    started = asyncio.Event()

    async def slow(input_value, ctx):
        started.set()
        await asyncio.sleep(5.0)
        return "never"

    runtime.register_agent("slow", slow)
    handle = await client.submit(agent="slow")
    await started.wait()
    await client.cancel_job(handle.job_id)
    # §7.4: cancellation is surfaced as job.error/CANCELLED, so the terminal
    # future raises the mapped error (#65).
    from arcp import ARCPCancelledError

    with pytest.raises(ARCPCancelledError):
        await handle.done
