"""Integration tests for job lifecycle (RFC §10)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime


async def _drain_until(
    client: ARCPClient,
    predicate: Callable[[Envelope], bool],
    *,
    timeout: float = 2.0,
) -> list[Envelope]:
    collected: list[Envelope] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    async for env in client.events():
        collected.append(env)
        if predicate(env):
            return collected
        if loop.time() > deadline:
            raise AssertionError(
                f"timeout waiting; received types: {[e.type for e in collected]}"
            )
    return collected


@pytest.mark.asyncio
async def test_tool_invoke_full_lifecycle(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def echo(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        await ctx.progress(percent=50, message="halfway")
        return {"echo": args}

    runtime.register_tool("echo", echo)
    accepted = await client.open()

    invoke = Envelope(
        id="msg_invoke_1",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "echo", "arguments": {"x": 1}},
    )
    await client.send(invoke)

    received = await _drain_until(
        client, lambda e: e.type == "job.completed", timeout=3.0
    )
    types = [e.type for e in received]
    assert "job.accepted" in types
    assert "job.started" in types
    assert "job.progress" in types
    assert "tool.result" in types
    assert "job.completed" in types

    result_env = next(e for e in received if e.type == "tool.result")
    assert result_env.payload["value"] == {"echo": {"x": 1}}


@pytest.mark.asyncio
async def test_tool_failure_emits_tool_error_and_job_failed(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def boom(ctx: JobContext, args: dict[str, Any]) -> Any:
        raise RuntimeError("kaboom")

    runtime.register_tool("boom", boom)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_b",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "boom", "arguments": {}},
    )
    await client.send(invoke)

    received = await _drain_until(client, lambda e: e.type == "job.failed", timeout=3.0)
    types = [e.type for e in received]
    assert "tool.error" in types
    assert "job.failed" in types
    err = next(e for e in received if e.type == "tool.error")
    assert err.payload["code"] == "INTERNAL"
    assert "kaboom" in err.payload["message"]


@pytest.mark.asyncio
async def test_unknown_tool_returns_not_found(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_u",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "missing", "arguments": {}},
    )
    nack = await client.request(invoke, timeout=2.0)
    assert nack.type == "nack"
    assert nack.payload["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_streaming_chunks_round_trip(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def streamer(ctx: JobContext, args: dict[str, Any]) -> str:
        sid = await ctx.open_stream(kind="text")
        for i in range(3):
            await ctx.chunk(sid, content=f"chunk-{i}")
        await ctx.close_stream(sid)
        return "done"

    runtime.register_tool("streamer", streamer)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_str_1",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "streamer", "arguments": {}},
    )
    await client.send(invoke)

    received = await _drain_until(
        client, lambda e: e.type == "job.completed", timeout=3.0
    )
    chunks = [e for e in received if e.type == "stream.chunk"]
    assert len(chunks) == 3
    sequences = [e.payload["sequence"] for e in chunks]
    assert sequences == [0, 1, 2]
    contents = [e.payload["content"] for e in chunks]
    assert contents == ["chunk-0", "chunk-1", "chunk-2"]


@pytest.mark.asyncio
async def test_thought_stream_carries_role_and_redacted(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def thinker(ctx: JobContext, args: dict[str, Any]) -> str:
        sid = await ctx.open_stream(kind="thought")
        await ctx.chunk(sid, content="reasoning step 1", role="assistant_thought", redacted=False)
        await ctx.chunk(sid, content="", role="assistant_thought", redacted=True)
        await ctx.close_stream(sid)
        return "ok"

    runtime.register_tool("thinker", thinker)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_thought",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "thinker", "arguments": {}},
    )
    await client.send(invoke)
    received = await _drain_until(
        client, lambda e: e.type == "job.completed", timeout=3.0
    )
    chunks = [e for e in received if e.type == "stream.chunk"]
    assert chunks[0].payload["role"] == "assistant_thought"
    assert chunks[0].payload["redacted"] is False
    assert chunks[1].payload["redacted"] is True
