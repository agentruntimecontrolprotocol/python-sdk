"""End-to-end test over a real WebSocket on localhost (RFC §22)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from websockets.asyncio.server import ServerConnection

from arcp.auth.bearer import StaticTokenValidator
from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.messages.session import AuthBlock, Capabilities, Identity, RuntimeIdentity
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime, RuntimeConfig
from arcp.transport.websocket import (
    WebSocketTransport,
    connect_websocket,
    ws_serve,
)
from tests.integration.conftest import default_advertised


@pytest.mark.asyncio
async def test_websocket_full_lifecycle() -> None:
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="rt", version="1"),
            advertised_capabilities=default_advertised(),
            bearer_validator=StaticTokenValidator({"good": "alice"}),
        )
    )
    await rt.start()

    async def echo(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"echo": args}

    rt.register_tool("echo", echo)

    async def _handler(ws: ServerConnection) -> None:
        await rt.serve_session(WebSocketTransport(ws))

    server = await ws_serve(_handler, "127.0.0.1", 0)
    sockets = list(server.sockets)
    assert sockets
    addr = sockets[0].getsockname()
    port = addr[1]

    transport = await connect_websocket(f"ws://127.0.0.1:{port}")
    client = ARCPClient(
        transport=transport,
        client_identity=Identity(kind="t", version="1"),
        auth=AuthBlock(scheme="bearer", token="good"),
        capabilities=Capabilities(
            streaming=True, human_input=True, artifacts=True, subscriptions=True
        ),
    )
    try:
        accepted = await client.open()
        invoke = Envelope(
            id="msg_inv_ws",
            type="tool.invoke",
            session_id=accepted.session_id,
            payload={"tool": "echo", "arguments": {"x": 1}},
        )
        await client.send(invoke)

        async def _wait_for_completion() -> Envelope:
            async for env in client.events():
                if env.type == "job.completed":
                    return env
            raise AssertionError("no job.completed")

        completion = await asyncio.wait_for(_wait_for_completion(), timeout=3.0)
        assert completion.payload["result"] == {"echo": {"x": 1}}
    finally:
        await client.close()
        server.close()
        try:
            await server.wait_closed()
        except Exception:
            pass
        await rt.close()
