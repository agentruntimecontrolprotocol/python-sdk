"""result_chunk — agent streams 30 chunks via `ctx.stream_result()` (§8.4)."""

from __future__ import annotations

import asyncio
import os

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7893"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def report_builder(input: dict, ctx: JobContext) -> None:
    chunks = int((input or {}).get("chunks", 30))
    async with ctx.stream_result() as stream:
        for i in range(1, chunks + 1):
            await stream.write(f"Section {i}: lorem ipsum dolor sit amet.\n".encode())
        await stream.close(summary=f"report with {chunks} chunks")


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="result-chunk-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("report-builder", report_builder)
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
