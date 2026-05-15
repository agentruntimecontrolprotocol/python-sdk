"""delegate — parent agent submits a child job; both share trace_id."""

from __future__ import annotations

import asyncio
import os

from arcp import ClientInfo, RuntimeInfo, WebSocketTransport, serve_websocket
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7878"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")
LOOPBACK = f"ws://127.0.0.1:{PORT}/arcp"


async def child_agent(input: dict, ctx: JobContext) -> dict:
    await ctx.log("info", "child running", attributes={"trace_id": ctx.trace_id})
    return {"child_done": True, "trace_id": ctx.trace_id}


async def parent_agent(input: dict, ctx: JobContext) -> dict:
    # Parent agent runs an in-process loopback client to invoke the child
    # so the child inherits trace_id over the wire (see spec §13.2).
    client = ARCPClient(
        client=ClientInfo(name="delegate-parent", version="1.0.0"),
        token=TOKEN,
        features=(),
    )
    transport = await WebSocketTransport.connect(LOOPBACK)
    try:
        await client.connect(transport)
        child = await client.submit(
            agent="child",
            input={"from": "parent"},
            trace_id=ctx.trace_id,
            parent_job_id=ctx.job_id,
        )
        await ctx.job.emit_event("delegate", {"child_job_id": child.job_id, "agent": "child"})
        async for _ in child.events():
            pass
        result = await child.done
    finally:
        await client.close()
    return {"parent_trace": ctx.trace_id, "child_trace": result.result.get("trace_id")}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="delegate-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("parent", parent_agent)
    runtime.register_agent("child", child_agent)
    server = await serve_websocket(runtime.accept, host="127.0.0.1", port=PORT, path="/arcp")
    print(f"listening on {LOOPBACK}")
    try:
        await asyncio.Future()
    finally:
        server.close()
        await server.wait_closed()
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
