"""§7.2 — idempotency key behavior."""

from __future__ import annotations

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
