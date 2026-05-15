"""list_jobs — runtime advertises list_jobs feature; jobs persist long enough to list."""

from __future__ import annotations

import asyncio
import os

from arcp import Capabilities, RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7887"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def hold(input: dict, ctx: JobContext) -> dict:
    # Stay running indefinitely so list_jobs can paginate them.
    while True:
        await asyncio.sleep(60)


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="list-jobs-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
        capabilities=Capabilities(encodings=("json",), features=("list_jobs",)),
    )
    runtime.register_agent("hold", hold)
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
