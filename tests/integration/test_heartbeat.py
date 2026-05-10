"""Heartbeat watchdog tests (RFC §10.3)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from arcp.auth.bearer import StaticTokenValidator
from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.messages.session import AuthBlock, Capabilities, Identity, RuntimeIdentity
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime, RuntimeConfig
from arcp.transport.in_memory import create_pair
from tests.integration.conftest import default_advertised


@pytest.fixture
async def fast_runtime() -> AsyncIterator[ARCPRuntime]:
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="rt", version="1"),
            advertised_capabilities=default_advertised(),
            bearer_validator=StaticTokenValidator({"good": "alice"}),
            heartbeat_interval_override=0.1,
            heartbeat_miss_threshold=2,
        )
    )
    await rt.start()
    try:
        yield rt
    finally:
        await rt.close()


@pytest.mark.asyncio
async def test_heartbeat_lost_when_no_heartbeats(fast_runtime: ARCPRuntime) -> None:
    async def silent(ctx: JobContext, args: dict[str, Any]) -> str:
        await asyncio.sleep(2.0)
        return "ok"

    fast_runtime.register_tool("silent", silent)
    client_t, server_t = create_pair()
    server_task = asyncio.create_task(fast_runtime.serve_session(server_t))
    client = ARCPClient(
        transport=client_t,
        client_identity=Identity(kind="t", version="1"),
        auth=AuthBlock(scheme="bearer", token="good"),
        capabilities=Capabilities(streaming=True, durable_jobs=True, human_input=True, artifacts=True, subscriptions=True),
    )
    try:
        accepted = await client.open()
        invoke = Envelope(
            id="msg_silent",
            type="tool.invoke",
            session_id=accepted.session_id,
            payload={"tool": "silent", "arguments": {}},
        )
        await client.send(invoke)
        # Wait for job.failed with HEARTBEAT_LOST.
        async def _await_failed() -> Envelope:
            async for env in client.events():
                if env.type == "job.failed":
                    return env
            raise AssertionError("never failed")

        failed = await asyncio.wait_for(_await_failed(), timeout=3.0)
        assert failed.payload["code"] == "HEARTBEAT_LOST"
    finally:
        await client.close()
        server_task.cancel()
        try:
            await server_task
        except BaseException:
            pass


@pytest.mark.asyncio
async def test_heartbeat_emitted_keeps_job_alive(fast_runtime: ARCPRuntime) -> None:
    async def steady(ctx: JobContext, args: dict[str, Any]) -> str:
        for _ in range(8):
            await ctx.heartbeat(deadline_ms=200)
            await asyncio.sleep(0.05)
        return "alive"

    fast_runtime.register_tool("steady", steady)
    client_t, server_t = create_pair()
    server_task = asyncio.create_task(fast_runtime.serve_session(server_t))
    client = ARCPClient(
        transport=client_t,
        client_identity=Identity(kind="t", version="1"),
        auth=AuthBlock(scheme="bearer", token="good"),
        capabilities=Capabilities(streaming=True, durable_jobs=True, human_input=True, artifacts=True, subscriptions=True),
    )
    try:
        accepted = await client.open()
        invoke = Envelope(
            id="msg_steady",
            type="tool.invoke",
            session_id=accepted.session_id,
            payload={"tool": "steady", "arguments": {}},
        )
        await client.send(invoke)
        types_seen: list[str] = []
        async for env in client.events():
            types_seen.append(env.type)
            if env.type == "job.completed":
                break
        assert "job.heartbeat" in types_seen
        assert "job.failed" not in types_seen
    finally:
        await client.close()
        server_task.cancel()
        try:
            await server_task
        except BaseException:
            pass
