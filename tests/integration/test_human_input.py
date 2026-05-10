"""Human-in-the-loop tests (RFC §12)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.messages.human import HumanChoiceOption
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime


def _iso_in_seconds(secs: float) -> str:
    when = datetime.now(tz=UTC) + timedelta(seconds=secs)
    return when.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


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
async def test_human_input_happy_path(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def asker(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        result = await ctx.request_human_input(
            prompt="What branch?",
            response_schema={"type": "object"},
            expires_at=_iso_in_seconds(5),
        )
        return result

    runtime.register_tool("asker", asker)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_h",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "asker", "arguments": {}},
    )
    await client.send(invoke)

    request = await _drain_until(client, lambda e: e.type == "human.input.request", timeout=2.0)
    request_env = request[-1]

    response = Envelope(
        id="msg_resp_1",
        type="human.input.response",
        session_id=accepted.session_id,
        correlation_id=request_env.id,
        payload={"value": {"branch": "fix/x"}, "responded_by": "test"},
    )
    await client.send(response)

    final = await _drain_until(client, lambda e: e.type == "job.completed", timeout=3.0)
    result_env = next(e for e in final if e.type == "tool.result")
    assert result_env.payload["value"] == {"branch": "fix/x"}


@pytest.mark.asyncio
async def test_human_input_default_used_on_timeout(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def asker(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return await ctx.request_human_input(
            prompt="quick?",
            default={"branch": "fallback"},
            expires_at=_iso_in_seconds(0.2),
        )

    runtime.register_tool("asker_default", asker)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_def",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "asker_default", "arguments": {}},
    )
    await client.send(invoke)
    final = await _drain_until(client, lambda e: e.type == "job.completed", timeout=3.0)
    types = [e.type for e in final]
    assert "human.input.cancelled" in types
    result = next(e for e in final if e.type == "tool.result")
    assert result.payload["value"] == {"branch": "fallback"}


@pytest.mark.asyncio
async def test_human_input_no_default_fails_on_expiry(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def asker(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return await ctx.request_human_input(
            prompt="strict",
            expires_at=_iso_in_seconds(0.2),
        )

    runtime.register_tool("asker_strict", asker)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_strict",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "asker_strict", "arguments": {}},
    )
    await client.send(invoke)
    final = await _drain_until(client, lambda e: e.type == "job.failed", timeout=3.0)
    failed = next(e for e in final if e.type == "job.failed")
    assert failed.payload["code"] == "DEADLINE_EXCEEDED"


@pytest.mark.asyncio
async def test_human_choice_round_trip(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def chooser(ctx: JobContext, args: dict[str, Any]) -> str:
        return await ctx.request_human_choice(
            prompt="how?",
            options=[
                HumanChoiceOption(id="a", label="A"),
                HumanChoiceOption(id="b", label="B"),
            ],
            expires_at=_iso_in_seconds(5),
        )

    runtime.register_tool("chooser", chooser)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_c",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "chooser", "arguments": {}},
    )
    await client.send(invoke)
    request = await _drain_until(client, lambda e: e.type == "human.choice.request", timeout=2.0)
    response = Envelope(
        id="msg_resp_c",
        type="human.choice.response",
        session_id=accepted.session_id,
        correlation_id=request[-1].id,
        payload={"choice_id": "b"},
    )
    await client.send(response)
    final = await _drain_until(client, lambda e: e.type == "job.completed", timeout=3.0)
    result = next(e for e in final if e.type == "tool.result")
    assert result.payload["value"] == "b"
