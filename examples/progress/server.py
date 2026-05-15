"""progress — agent emits §8.2.1 `progress` events with current/total/units."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7892"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def report_agent(input: dict, ctx: JobContext) -> dict:
    total = int((input or {}).get("steps", 10))
    for i in range(1, total + 1):
        await ctx.progress(i, total=total, units="steps", message=f"step {i}/{total}")
        await asyncio.sleep(0.02)
    return {"steps": total}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="progress-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("report", report_agent)
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
