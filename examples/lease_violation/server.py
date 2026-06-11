"""lease_violation — agent attempts an out-of-lease op, observes PERMISSION_DENIED, continues."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7882"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def cautious_agent(input: dict, ctx: JobContext) -> dict:
    # Try fs.write to a path NOT covered by the lease (lease only allows fs.read).
    try:
        ctx.authorize("fs.write", "/etc/passwd")
        outcome = {"result": "wrote"}
    except Exception as e:  # PermissionDeniedError
        outcome = {"error": {"code": "PERMISSION_DENIED", "message": str(e), "retryable": False}}
    await ctx.tool_result({"call_id": "tc1", **outcome})
    await ctx.log("info", "agent continues after lease violation")
    return {"continued": True}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="lease-violation-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("cautious", cautious_agent)
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
