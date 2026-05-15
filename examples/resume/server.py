"""resume — slow-emitting agent so the client can disconnect mid-stream."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7880"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def slow_agent(input: dict, ctx: JobContext) -> dict:
    for i in range(10):
        await ctx.log("info", f"step {i}", attributes={"i": i})
        await asyncio.sleep(0.5)
    return {"steps": 10}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="resume-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
        # Wide resume window so the client has time to reconnect.
        resume_window_sec=60,
    )
    runtime.register_agent("slow", slow_agent)
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
