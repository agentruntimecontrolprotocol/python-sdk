"""02 — tool invocation with progress and a text stream.

Demonstrates RFC §10 (jobs) and §11 (streaming).
"""

from __future__ import annotations

import asyncio
from typing import Any

from _common import runtime_and_client

from arcp.envelope import Envelope
from arcp.runtime.job import JobContext


async def search_files(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
    sid = await ctx.open_stream(kind="text")
    matches: list[str] = []
    for i, name in enumerate(args.get("files", [])):
        await ctx.progress(percent=(i + 1) * 100 / max(1, len(args.get("files", []))))
        await ctx.chunk(sid, content=f"matched: {name}")
        matches.append(name)
    await ctx.close_stream(sid)
    return {"matches": matches}


async def main() -> None:
    async with runtime_and_client() as (rt, client):
        rt.register_tool("search", search_files)
        accepted = await client.open()

        invoke = Envelope(
            id="msg_invoke_search",
            type="tool.invoke",
            session_id=accepted.session_id,
            payload={
                "tool": "search",
                "arguments": {"files": ["a.ts", "b.ts", "c.ts"]},
            },
        )
        await client.send(invoke)

        async for env in client.events():
            print(f"<< {env.type}: {env.payload}")
            if env.type == "job.completed":
                break


if __name__ == "__main__":
    asyncio.run(main())
