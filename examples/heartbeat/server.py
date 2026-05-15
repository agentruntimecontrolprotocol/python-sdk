"""heartbeat — runtime declares a 5s heartbeat interval; client replies with pongs."""

from __future__ import annotations

import asyncio
import os

from arcp import Capabilities, RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7885"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def long_agent(input: dict, ctx: JobContext) -> dict:
    # Long enough that >= 2 heartbeats round-trip during the job.
    await asyncio.sleep(12)
    return {"ok": True}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="heartbeat-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
        capabilities=Capabilities(encodings=("json",), features=("heartbeat",)),
        heartbeat_interval_sec=5,
    )
    runtime.register_agent("long", long_agent)
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
