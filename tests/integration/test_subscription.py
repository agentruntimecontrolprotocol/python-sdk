"""Subscription tests (RFC §13)."""

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
async def test_subscribe_receives_live_events(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def echo(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        await ctx.progress(percent=33, message="thirty three")
        return {"ok": True}

    runtime.register_tool("echo", echo)
    accepted = await client.open()

    sub = Envelope(
        id="msg_sub_live",
        type="subscribe",
        session_id=accepted.session_id,
        payload={"filter": {"types": ["job.progress", "job.completed"]}},
    )
    sub_accepted = await client.request(sub, timeout=2.0)
    assert sub_accepted.type == "subscribe.accepted"

    invoke = Envelope(
        id="msg_inv_x",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "echo", "arguments": {}},
    )
    await client.send(invoke)

    received = await _drain_until(
        client,
        lambda e: e.type == "subscribe.event" and e.payload["event"]["type"] == "job.completed",
        timeout=3.0,
    )
    sub_events = [e for e in received if e.type == "subscribe.event"]
    inner_types = [e.payload["event"]["type"] for e in sub_events]
    assert "job.progress" in inner_types
    assert "job.completed" in inner_types
    # min_priority filter not set → no priority filtering kicked in.


@pytest.mark.asyncio
async def test_subscribe_backfill_then_live(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def echo(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    runtime.register_tool("echo", echo)
    accepted = await client.open()

    invoke = Envelope(
        id="msg_inv_bf",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "echo", "arguments": {}},
    )
    await client.send(invoke)
    pre = await _drain_until(client, lambda e: e.type == "job.completed", timeout=2.0)
    earliest_id = next(e.id for e in pre if e.type == "job.accepted")

    sub = Envelope(
        id="msg_sub_bf",
        type="subscribe",
        session_id=accepted.session_id,
        payload={
            "filter": {"types": ["job.completed", "subscription.backfill_complete"]},
            "since": {"after_message_id": earliest_id},
        },
    )
    await client.request(sub, timeout=2.0)

    received = await _drain_until(
        client,
        lambda e: (
            e.type == "subscribe.event"
            and e.payload["event"]["type"] == "subscription.backfill_complete"
        ),
        timeout=3.0,
    )
    inner = [e.payload["event"]["type"] for e in received if e.type == "subscribe.event"]
    assert "job.completed" in inner
    assert "subscription.backfill_complete" in inner
    bf_complete = next(
        e
        for e in received
        if e.type == "subscribe.event"
        and e.payload["event"]["type"] == "subscription.backfill_complete"
    )
    assert bf_complete.payload["event"]["payload"]["event_count"] >= 1


@pytest.mark.asyncio
async def test_unauthorized_subscription_rejected(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()

    sub = Envelope(
        id="msg_sub_bad",
        type="subscribe",
        session_id=accepted.session_id,
        payload={"filter": {"session_id": ["sess_other"]}},
    )
    nack = await client.request(sub, timeout=2.0)
    assert nack.type == "nack"
    assert nack.payload["code"] == "PERMISSION_DENIED"
