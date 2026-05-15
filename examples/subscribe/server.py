"""subscribe — runtime uses an allow-all policy for subscribe/list; cancel still requires submitter."""

from __future__ import annotations

import asyncio
import os

from arcp import Capabilities, RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, AuthorizationContext, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7888"))
TOKEN_A = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")
TOKEN_B = "demo-token-b"


async def slow_agent(input: dict, ctx: JobContext) -> dict:
    for i in range(20):
        await ctx.log("info", f"step {i}", attributes={"i": i})
        await asyncio.sleep(0.3)
    return {"steps": 20}


def open_authz(ctx: AuthorizationContext) -> bool:
    """List/subscribe open to any authenticated session; cancel is still submitter-only."""
    if ctx.operation in ("list", "subscribe"):
        return True
    return ctx.job.submitter_principal == ctx.requester_principal


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="subscribe-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN_A: "principal-a", TOKEN_B: "principal-b"}),
        capabilities=Capabilities(encodings=("json",), features=("list_jobs", "subscribe")),
        job_authorization_policy=open_authz,
    )
    runtime.register_agent("slow", slow_agent)
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
