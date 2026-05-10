"""Tests for the ClientHandlers default resolver wiring."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from arcp.client.client import ARCPClient
from arcp.client.handlers import ClientHandlers
from arcp.envelope import Envelope
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime


def _iso_in(secs: float) -> str:
    return (datetime.now(tz=UTC) + timedelta(seconds=secs)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.asyncio
async def test_client_handlers_resolve_human_input(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def asker(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return await ctx.request_human_input(
            prompt="?", expires_at=_iso_in(5), response_schema={"type": "object"}
        )

    runtime.register_tool("asker_h", asker)
    accepted = await client.open()

    async def _resolver(env: Envelope) -> dict[str, Any]:
        return {"branch": "x"}

    completion: asyncio.Future[Envelope] = asyncio.get_running_loop().create_future()

    async def _pump_and_capture() -> None:
        async for env in client.events():
            if env.type == "human.input.request":
                value = await _resolver(env)
                await client.send(
                    Envelope(
                        id=f"r_{env.id}",
                        type="human.input.response",
                        session_id=env.session_id,
                        correlation_id=env.id,
                        payload={"value": value},
                    )
                )
            if env.type == "job.completed" and not completion.done():
                completion.set_result(env)
                return

    pump = asyncio.create_task(_pump_and_capture())

    invoke = Envelope(
        id="msg_inv_h",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "asker_h", "arguments": {}},
    )
    await client.send(invoke)
    final = await asyncio.wait_for(completion, timeout=3.0)
    pump.cancel()
    with contextlib.suppress(BaseException):
        await pump
    assert final.type == "job.completed"


@pytest.mark.asyncio
async def test_client_handlers_grant_via_helper(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def writer(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return await ctx.request_permission(permission="x.write", requested_lease_seconds=60)

    runtime.register_tool("writer_h", writer)
    accepted = await client.open()

    async def _decide(env: Envelope) -> tuple[bool, str | None]:
        return (True, None)

    handlers = ClientHandlers(client=client, permission=_decide)
    pump = asyncio.create_task(handlers.pump())

    invoke = Envelope(
        id="msg_inv_writer_h",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "writer_h", "arguments": {}},
    )
    await client.send(invoke)
    # The pump owns events; let it run a bit then cancel.
    await asyncio.sleep(0.5)
    pump.cancel()
    with contextlib.suppress(BaseException):
        await pump
