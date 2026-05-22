"""End-to-end happy path over a real localhost WebSocket loopback."""

from __future__ import annotations

import asyncio
import contextlib
import os

import pytest

from arcp import ClientInfo, RuntimeInfo, WebSocketTransport, serve_websocket
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, JobContext, StaticBearerVerifier


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="localhost websockets intermittently hang on GitHub Linux runners",
)
async def test_websocket_submit_and_done() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )

    async def echo(input_value, ctx: JobContext):
        return {"echoed": input_value}

    rt.register_agent("echo", echo)

    port = 0
    server = await serve_websocket(rt.accept, host="127.0.0.1", port=port, path="/arcp")
    try:
        assert server.sockets is not None
        bound_port = server.sockets[0].getsockname()[1]
        client = ARCPClient(client=ClientInfo(name="c", version="1"), token="tok")
        transport = await WebSocketTransport.connect(f"ws://127.0.0.1:{bound_port}/arcp")
        try:
            await client.connect(transport)
            handle = await client.submit(agent="echo", input={"hi": 1})
            result = await handle.done
            assert result.final_status == "success"
            assert result.result == {"echoed": {"hi": 1}}
        finally:
            await client.close()
    finally:
        server.close(close_connections=True)
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(server.wait_closed(), timeout=2.0)
        await rt.close()
