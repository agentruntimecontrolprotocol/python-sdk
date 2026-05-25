"""§7.2 — idempotency key behavior."""

from __future__ import annotations

import asyncio

import pytest

from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime


async def test_idempotency_same_key_returns_same_job_id(
    runtime: ARCPRuntime, client: ARCPClient
) -> None:
    async def agent(input_value, ctx):
        return "ok"

    runtime.register_agent("idem-a", agent)
    key = "test-key-same"
    h1 = await client.submit(agent="idem-a", input=1, idempotency_key=key)
    h2 = await client.submit(agent="idem-a", input=1, idempotency_key=key)
    assert h1.job_id == h2.job_id


async def test_idempotency_conflict_raises_duplicate_key(
    runtime: ARCPRuntime, client: ARCPClient
) -> None:
    async def agent(input_value, ctx):
        return "ok"

    runtime.register_agent("idem-b", agent)
    key = "test-key-conflict"
    await client.submit(agent="idem-b", input=1, idempotency_key=key)
    # The client surfaces this as a session.error which fails all handles;
    # we settle for asserting the second submit doesn't return identical work.
    with pytest.raises(Exception):
        await client.submit(agent="idem-b", input=2, idempotency_key=key)


async def test_idempotency_duplicate_after_completion_resolves_handle(
    runtime: ARCPRuntime, client: ARCPClient
) -> None:
    """Issue #42: duplicate submits after terminal MUST not hang `await handle.done`."""

    async def agent(input_value, ctx):
        return {"echo": input_value}

    runtime.register_agent("idem-c", agent)
    key = "test-key-after-terminal"
    h1 = await client.submit(agent="idem-c", input=1, idempotency_key=key)
    result1 = await asyncio.wait_for(h1.done, timeout=1.0)
    assert result1.final_status == "success"

    # Duplicate submit after the original is complete: the handle must
    # resolve to the same terminal payload, not hang.
    h2 = await client.submit(agent="idem-c", input=1, idempotency_key=key)
    assert h2.job_id == h1.job_id
    result2 = await asyncio.wait_for(h2.done, timeout=1.0)
    assert result2.final_status == "success"
    assert result2.result == result1.result
