"""host_asgi — Starlette + uvicorn mounting `arcp_asgi_app(runtime)` at /arcp."""

from __future__ import annotations

import os
import sys

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute

from arcp import RuntimeInfo
from arcp.middleware.asgi import arcp_asgi_app
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7896"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


async def echo(input: dict, ctx: JobContext) -> dict:
    return {"echoed": input}


async def health(request):
    return JSONResponse({"ok": True, "request_id": str(id(request))})


def build_app() -> Starlette:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="host-asgi-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("echo", echo)
    return Starlette(
        routes=[
            Route("/health", health),
            WebSocketRoute(
                "/arcp",
                endpoint=arcp_asgi_app(runtime, allowed_hosts=["localhost", "127.0.0.1"]),
            ),
        ]
    )


if __name__ == "__main__":
    sys.stdout.write(f"listening on http://127.0.0.1:{PORT}\n")
    sys.stdout.flush()
    uvicorn.run(build_app(), host="127.0.0.1", port=PORT, log_level="warning")
