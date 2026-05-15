"""§14 — chunks larger than the size cap raise INTERNAL_ERROR."""

from __future__ import annotations

from arcp import InternalError
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime


async def test_chunk_size_cap_enforced(runtime: ARCPRuntime, client: ARCPClient) -> None:
    captured: list[Exception] = []

    async def big_chunk(input_value, ctx):
        big = "x" * (ctx.chunk_size_cap + 100)
        try:
            await ctx.result_chunk(
                {"result_id": "r1", "chunk_seq": 0, "data": big, "encoding": "utf8", "more": True}
            )
        except InternalError as e:
            captured.append(e)
        return "ok"

    runtime.register_agent("big", big_chunk)
    handle = await client.submit(agent="big")
    await handle.done
    assert len(captured) == 1
