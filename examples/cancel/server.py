"""cancel — long-running agent that observes ctx.signal / CancelledError."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7883"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def patient_agent(input: dict, ctx: JobContext) -> dict:
    # Single cancellation channel: when the runtime cancels the job task,
    # the in-flight `await` raises CancelledError. The runtime emits
    # `job.error { final_status: "cancelled" }` on the way out.
    for i in range(60):
        await ctx.log("info", f"tick {i}")
        await asyncio.sleep(0.5)
    return {"never_reached": True}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="cancel-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("patient", patient_agent)
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
