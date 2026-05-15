"""vendor_extensions — agent emits x-vendor.acme.* event kinds and uses a vendor lease ns."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7884"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def vendor_agent(input: dict, ctx: JobContext) -> dict:
    # Emit a reserved status, then a vendor event kind.
    await ctx.status("starting")
    for i in range(1, 4):
        await ctx.job.emit_event("x-vendor.acme.progress", {"i": i, "total": 3})
        await asyncio.sleep(0.1)
    await ctx.status("complete")
    return {"vendor": True}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="vendor-extensions-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("vendor", vendor_agent)
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
