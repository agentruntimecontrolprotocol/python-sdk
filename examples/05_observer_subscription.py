"""05 — observer subscription.

Demonstrates RFC §13: a separate subscription opened by the same session
receives every event matching its filter.
"""

from __future__ import annotations

import asyncio
from typing import Any

from _common import runtime_and_client

from arcp.envelope import Envelope
from arcp.runtime.job import JobContext


async def echo(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
    await ctx.progress(percent=25, message="quarter")
    await ctx.progress(percent=75, message="three quarters")
    return {"echo": args}


async def main() -> None:
    async with runtime_and_client() as (rt, client):
        rt.register_tool("echo", echo)
        accepted = await client.open()

        sub = Envelope(
            id="msg_sub",
            type="subscribe",
            session_id=accepted.session_id,
            payload={"filter": {"types": ["job.progress", "job.completed"]}},
        )
        await client.request(sub, timeout=2.0)

        invoke = Envelope(
            id="msg_invoke_echo",
            type="tool.invoke",
            session_id=accepted.session_id,
            payload={"tool": "echo", "arguments": {"x": 1}},
        )
        await client.send(invoke)

        async for env in client.events():
            if env.type == "subscribe.event":
                inner = env.payload["event"]
                print(f"observed: {inner['type']} {inner.get('payload', {})}")
                if inner["type"] == "job.completed":
                    break


if __name__ == "__main__":
    asyncio.run(main())
