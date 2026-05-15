"""lease_expires_at — lease constraint with `expires_at`; watchdog emits LEASE_EXPIRED."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7890"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def slow(input: dict, ctx: JobContext) -> dict:
    # Sleep past the lease expiry. The runtime watchdog will cancel this
    # task and emit `job.error{LEASE_EXPIRED}` before the sleep returns.
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        await ctx.log("warn", "agent observed cancellation from lease expiry")
        raise
    return {"ok": True}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="lease-expires-at-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("slow", slow)
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
