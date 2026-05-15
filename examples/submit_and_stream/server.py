"""submit_and_stream — agent emits 7 reserved event kinds and a terminal job.result."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7879"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def echo_agent(input: dict, ctx: JobContext) -> dict:
    await ctx.status("starting")
    await ctx.log("info", "agent received input", attributes={"keys": list((input or {}).keys())})
    await ctx.thought("I will fetch then summarize.")
    await ctx.tool_call({"tool_call_id": "tc1", "name": "fetch", "arguments": {"url": "x://"}})
    await ctx.tool_result({"tool_call_id": "tc1", "output": {"bytes": 42}})
    await ctx.metric({"name": "tokens.in", "value": 12, "unit": "tokens"})
    await ctx.job.emit_event(
        "artifact_ref",
        {
            "artifact_id": "a1",
            "media_type": "text/plain",
            "size_bytes": 7,
            "summary": "report",
        },
    )
    await ctx.status("complete")
    return {"summary": "ok"}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="submit-and-stream-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("echo", echo_agent)
    server = await serve_websocket(runtime.accept, host="127.0.0.1", port=PORT, path="/arcp")
    print(f"listening on ws://127.0.0.1:{PORT}/arcp")
    try:
        await asyncio.Future()
    finally:
        server.close()
        await server.wait_closed()
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
