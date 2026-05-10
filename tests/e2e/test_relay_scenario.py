"""End-to-end relay scenario, parametrized over WebSocket and stdio transports.

Mirrors the agent-relay example: an agent invokes a tool that requests
human approval, gets a response, produces an artifact, and completes.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from websockets.asyncio.server import ServerConnection

from arcp.auth.bearer import StaticTokenValidator
from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.messages.session import AuthBlock, Capabilities, Identity, RuntimeIdentity
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime, RuntimeConfig
from arcp.transport.base import Transport
from arcp.transport.websocket import (
    WebSocketTransport,
    connect_websocket,
    ws_serve,
)
from tests.integration.conftest import default_advertised
from tests.integration.test_stdio_transport import make_stdio_pipe_pair


async def _deploy(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
    grant = await ctx.request_permission(
        permission="deploy.execute",
        resource="env:staging",
        operation="rollout",
        requested_lease_seconds=60,
    )
    expires = (datetime.now(tz=UTC) + timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    confirm = await ctx.request_human_input(
        prompt="confirm?",
        response_schema={"type": "object"},
        expires_at=expires,
    )
    return {"lease_id": grant["lease_id"], "by": confirm.get("by")}


async def _client_loop(client: ARCPClient, accepted_id: str) -> str | None:
    """Drive the client side: respond to prompts, then upload an artifact."""

    invoke = Envelope(
        id="msg_inv_e2e",
        type="tool.invoke",
        session_id=accepted_id,
        payload={"tool": "deploy", "arguments": {}},
    )
    await client.send(invoke)
    async for env in client.events():
        if env.type == "permission.request":
            await client.send(
                Envelope(
                    id=f"grant_{env.id}",
                    type="permission.grant",
                    session_id=accepted_id,
                    correlation_id=env.id,
                    payload={
                        "permission": env.payload["permission"],
                        "lease_seconds": 60,
                    },
                )
            )
        elif env.type == "human.input.request":
            await client.send(
                Envelope(
                    id=f"resp_{env.id}",
                    type="human.input.response",
                    session_id=accepted_id,
                    correlation_id=env.id,
                    payload={"value": {"by": "alice"}},
                )
            )
        elif env.type == "job.completed":
            ref = await client.request(
                Envelope(
                    id="msg_art_e2e",
                    type="artifact.put",
                    session_id=accepted_id,
                    payload={
                        "media_type": "text/plain",
                        "size": 13,
                        "data": base64.b64encode(b"deploy-log\n").decode("ascii"),
                    },
                ),
                timeout=2.0,
            )
            return ref.payload["artifact_id"]
    return None


def _make_runtime() -> ARCPRuntime:
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="rt", version="1"),
            advertised_capabilities=default_advertised(),
            bearer_validator=StaticTokenValidator({"good": "alice"}),
        )
    )
    rt.register_tool("deploy", _deploy)
    return rt


@pytest.mark.asyncio
async def test_relay_scenario_websocket() -> None:
    rt = _make_runtime()
    await rt.start()

    async def _handler(ws: ServerConnection) -> None:
        await rt.serve_session(WebSocketTransport(ws))

    server = await ws_serve(_handler, "127.0.0.1", 0)
    sockets = list(server.sockets)
    assert sockets
    port = sockets[0].getsockname()[1]
    transport: Transport = await connect_websocket(f"ws://127.0.0.1:{port}")
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
        artifact_id = await asyncio.wait_for(_client_loop(client, accepted.session_id), timeout=5.0)
        assert artifact_id is not None
        assert artifact_id.startswith("art_")
    finally:
        await client.close()
        server.close()
        try:
            await server.wait_closed()
        except Exception:
            pass
        await rt.close()


@pytest.mark.asyncio
async def test_relay_scenario_stdio() -> None:
    rt = _make_runtime()
    await rt.start()
    client_t, server_t = make_stdio_pipe_pair()
    server_task = asyncio.create_task(rt.serve_session(server_t))
    client = ARCPClient(
        transport=client_t,
        client_identity=Identity(kind="t", version="1"),
        auth=AuthBlock(scheme="bearer", token="good"),
        capabilities=Capabilities(
            streaming=True, human_input=True, artifacts=True, subscriptions=True
        ),
    )
    try:
        accepted = await client.open()
        artifact_id = await asyncio.wait_for(_client_loop(client, accepted.session_id), timeout=5.0)
        assert artifact_id is not None
        assert artifact_id.startswith("art_")
    finally:
        await client.close()
        server_task.cancel()
        try:
            await server_task
        except BaseException:
            pass
        await rt.close()
