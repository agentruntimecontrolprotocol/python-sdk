"""stdio server — runs ARCP over the process's own stdin/stdout."""

from __future__ import annotations

import asyncio
import os
import sys

from arcp import RuntimeInfo, StdioTransport
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def echo_agent(input: dict, ctx: JobContext) -> dict:
    await ctx.log("info", "stdio agent ran")
    return {"echoed": input}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="stdio-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("echo", echo_agent)
    transport = await StdioTransport.from_std_streams()
    # All status output must go to stderr so it doesn't corrupt the NDJSON wire.
    print("stdio-server: handshake awaiting on stdin", file=sys.stderr)
    try:
        await runtime.accept(transport)
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
