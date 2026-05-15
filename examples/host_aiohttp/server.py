"""host_aiohttp — aiohttp.web hosting ARCP via serve_arcp_aiohttp."""

from __future__ import annotations

import asyncio
import os

from aiohttp import web

from arcp import RuntimeInfo
from arcp.middleware.aiohttp import arcp_aiohttp_handler
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7897"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def echo(input: dict, ctx: JobContext) -> dict:
    return {"echoed": input}


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="host-aiohttp-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("echo", echo)

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get(
        "/arcp",
        arcp_aiohttp_handler(runtime, allowed_hosts=["localhost", "127.0.0.1"]),
    )
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=PORT)
    await site.start()
    print(f"listening on http://127.0.0.1:{PORT}")
    try:
        await asyncio.Future()
    finally:
        await runner.cleanup()
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
