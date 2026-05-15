"""idempotent_retry — runtime deduplicates submits sharing (principal, idempotency_key)."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7881"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def echo_a(input: dict, ctx: JobContext) -> dict:
    return {"agent": "a", "input": input}


async def echo_b(input: dict, ctx: JobContext) -> dict:
    return {"agent": "b", "input": input}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="idempotent-retry-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("a", echo_a)
    runtime.register_agent("b", echo_b)
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
