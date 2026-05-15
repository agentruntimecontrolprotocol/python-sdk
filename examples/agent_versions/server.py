"""agent_versions — register multiple versions; welcome carries rich AgentInventoryEntry."""

from __future__ import annotations

import asyncio
import os

from arcp import Capabilities, RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7889"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def make_summarize(version: str):
    async def _agent(input: dict, ctx: JobContext) -> dict:
        return {"version": version, "len": len(str(input))}

    return _agent


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="agent-versions-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
        capabilities=Capabilities(encodings=("json",), features=("agent_versions",)),
    )
    runtime.register_agent_version("summarize", "1.0.0", await make_summarize("1.0.0"))
    runtime.register_agent_version("summarize", "1.2.3", await make_summarize("1.2.3"))
    runtime.set_default_agent_version("summarize", "1.2.3")
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
