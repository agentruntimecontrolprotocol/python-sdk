"""host_tracing — OTel ConsoleSpanExporter on both sides; trace stitches across the wire."""

from __future__ import annotations

import asyncio
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from arcp import RuntimeInfo, serve_websocket
from arcp.middleware.otel import with_tracing
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7895"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


def configure_tracer() -> trace.Tracer:
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("arcp.examples.host_tracing.server")


async def echo(input: dict, ctx: JobContext) -> dict:
    await ctx.log("info", "echo started")
    return {"echoed": input}


async def main() -> None:
    tracer = configure_tracer()
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="host-tracing-server", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
    )
    runtime.register_agent("echo", echo)

    async def traced_accept(transport):
        await runtime.accept(with_tracing(transport, tracer=tracer))

    server = await serve_websocket(traced_accept, host="127.0.0.1", port=PORT, path="/arcp")
    print(f"listening on ws://127.0.0.1:{PORT}/arcp")
    try:
        await asyncio.Future()
    finally:
        server.close()
        await server.wait_closed()
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
