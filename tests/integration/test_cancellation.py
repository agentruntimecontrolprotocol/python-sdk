"""Cancellation tests (RFC §10.4)."""

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
            raise AssertionError(
                f"timeout waiting; received types: {[e.type for e in collected]}"
            )
    return collected


@pytest.mark.asyncio
async def test_cooperative_cancel_yields_job_cancelled(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def slow(ctx: JobContext, args: dict[str, Any]) -> str:
        for _ in range(50):
            ctx.check_cancel()
            await asyncio.sleep(0.02)
        return "done"

    runtime.register_tool("slow", slow)
    accepted = await client.open()

    invoke = Envelope(
        id="msg_invoke_slow",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "slow", "arguments": {}},
    )
    await client.send(invoke)

    # Wait for job.started, then cancel.
    started = await _drain_until(
        client, lambda e: e.type == "job.started", timeout=2.0
    )
    job_id = started[-1].job_id
    assert job_id is not None

    cancel = Envelope(
        id="msg_cancel_1",
        type="cancel",
        session_id=accepted.session_id,
        payload={"target": "job", "target_id": job_id, "deadline_ms": 2000},
    )
    accept = await client.request(cancel, timeout=2.0)
    assert accept.type == "cancel.accepted"

    final = await _drain_until(
        client, lambda e: e.type in ("job.cancelled", "job.failed"), timeout=3.0
    )
    terminal = next(e for e in final if e.type in ("job.cancelled", "job.failed"))
    assert terminal.type == "job.cancelled"


@pytest.mark.asyncio
async def test_cancel_terminal_job_refused(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def fast(ctx: JobContext, args: dict[str, Any]) -> str:
        return "done"

    runtime.register_tool("fast", fast)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_fast",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "fast", "arguments": {}},
    )
    await client.send(invoke)
    received = await _drain_until(
        client, lambda e: e.type == "job.completed", timeout=2.0
    )
    job_id = next(e.job_id for e in received if e.type == "job.completed")
    assert job_id is not None

    cancel = Envelope(
        id="msg_cancel_late",
        type="cancel",
        session_id=accepted.session_id,
        payload={"target": "job", "target_id": job_id, "deadline_ms": 100},
    )
    refused = await client.request(cancel, timeout=2.0)
    assert refused.type == "cancel.refused"
    assert refused.payload["code"] == "FAILED_PRECONDITION"


@pytest.mark.asyncio
async def test_cancel_uncooperative_escalates_to_aborted(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    """A tool that ignores cancellation must be hard-killed past deadline → ABORTED."""

    client, runtime, _ = connected

    async def stubborn(ctx: JobContext, args: dict[str, Any]) -> str:
        # Deliberately never call ctx.check_cancel().
        await asyncio.sleep(5.0)
        return "stubborn"

    runtime.register_tool("stubborn", stubborn)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_stub",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "stubborn", "arguments": {}},
    )
    await client.send(invoke)
    started = await _drain_until(
        client, lambda e: e.type == "job.started", timeout=2.0
    )
    job_id = started[-1].job_id

    cancel = Envelope(
        id="msg_cancel_stub",
        type="cancel",
        session_id=accepted.session_id,
        payload={"target": "job", "target_id": job_id, "deadline_ms": 200},
    )
    await client.send(cancel)
    final = await _drain_until(
        client, lambda e: e.type in ("job.failed", "job.cancelled"), timeout=3.0
    )
    terminal = next(e for e in final if e.type in ("job.failed", "job.cancelled"))
    assert terminal.type == "job.failed"
    failed_payload = next(e for e in final if e.type == "job.failed")
    assert failed_payload.payload["code"] == "ABORTED"
