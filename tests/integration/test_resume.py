"""Resume tests (RFC §19)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.errors import ErrorCode
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime


async def _drain_until(
    client: ARCPClient,
    predicate: Callable[[Envelope], bool],
    *,
    timeout: float = 3.0,
) -> list[Envelope]:
    collected: list[Envelope] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    async for env in client.events():
        collected.append(env)
        if predicate(env):
            return collected
        if loop.time() > deadline:
            raise AssertionError(f"timeout; received types: {[e.type for e in collected]}")
    return collected


@pytest.mark.asyncio
async def test_resume_replays_after_anchor(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def echo(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    runtime.register_tool("echo", echo)
    accepted = await client.open()

    invoke = Envelope(
        id="msg_inv_resume",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "echo", "arguments": {}},
    )
    await client.send(invoke)
    completion = await _drain_until(client, lambda e: e.type == "job.completed", timeout=2.0)
    anchor = next(e.id for e in completion if e.type == "job.accepted")

    resume = Envelope(
        id="msg_resume",
        type="resume",
        session_id=accepted.session_id,
        payload={"after_message_id": anchor},
    )
    await client.send(resume)
    replayed = await _drain_until(client, lambda e: e.type == "job.completed", timeout=3.0)
    types = [e.type for e in replayed]
    assert "job.completed" in types
    assert "tool.result" in types


@pytest.mark.asyncio
async def test_resume_data_loss_when_anchor_missing(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()

    resume = Envelope(
        id="msg_resume_lost",
        type="resume",
        session_id=accepted.session_id,
        payload={"after_message_id": "msg_does_not_exist"},
    )
    nack = await client.request(resume, timeout=2.0)
    assert nack.type == "nack"
    assert nack.payload["code"] == ErrorCode.DATA_LOSS.value


@pytest.mark.asyncio
async def test_resume_with_checkpoint_id_unimplemented(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()

    resume = Envelope(
        id="msg_resume_chk",
        type="resume",
        session_id=accepted.session_id,
        payload={"checkpoint_id": "chk_007"},
    )
    nack = await client.request(resume, timeout=2.0)
    assert nack.type == "nack"
    assert nack.payload["code"] == ErrorCode.UNIMPLEMENTED.value
