"""§8.4 — MUST NOT mix inline `result` and `result_chunk` in one job."""

from __future__ import annotations

from datetime import UTC

from arcp import InvalidRequestError
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime


async def test_inline_then_chunk_raises(runtime: ARCPRuntime, client: ARCPClient) -> None:
    captured: list[Exception] = []

    async def mixer(input_value, ctx):
        # Emit an inline result via direct send.
        from datetime import datetime

        from arcp._messages.execution import JobResultPayload

        await ctx.job.emit_result(
            JobResultPayload(
                final_status="success",
                result={"x": 1},
                completed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        )
        # Now try to stream a chunk.
        try:
            await ctx.result_chunk(
                {"result_id": "r1", "chunk_seq": 0, "data": "x", "encoding": "utf8", "more": True}
            )
        except InvalidRequestError as e:
            captured.append(e)

    runtime.register_agent("mixer", mixer)
    handle = await client.submit(agent="mixer")
    await handle.done
    assert len(captured) == 1
