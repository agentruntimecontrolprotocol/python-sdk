"""host_tracing client — wraps its transport with `with_tracing(...)`."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient
from arcp.middleware.otel import with_tracing

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7895"))
URL = os.environ.get("ARCP_DEMO_URL", f"ws://127.0.0.1:{PORT}/arcp")
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")


def configure_tracer() -> trace.Tracer:
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("arcp.examples.host_tracing.client")


async def main() -> int:
    tracer = configure_tracer()
    client = ARCPClient(
        client=ClientInfo(name="host-tracing-client", version="1.0.0"), token=TOKEN, features=()
    )
    async with contextlib.aclosing(client):
        transport = with_tracing(await WebSocketTransport.connect(URL), tracer=tracer)
        await client.connect(transport)
        handle = await client.submit(agent="echo", input={"k": 1})
        result = await handle.done
        print(f"job -> {result.final_status}")
        assert result.final_status == "success"
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
