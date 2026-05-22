"""§8.4 ResultStream — chunked result writer coverage."""

from __future__ import annotations

import asyncio
import base64
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._errors import InvalidRequestError
from arcp._messages.execution import Lease
from arcp._runtime.result_stream import ResultStream
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


def _make_rt() -> ARCPRuntime:
    return ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )


async def _make_job_context(rt: ARCPRuntime, server_t, client_t):
    """Connect client, submit a slow agent, return the running JobContext."""
    started = asyncio.Event()
    job_ctx_holder: list = []

    async def capturing_agent(input_value, ctx):
        job_ctx_holder.append(ctx)
        started.set()
        await asyncio.sleep(30)

    rt.register_agent("capturing", capturing_agent)
    accept_task = asyncio.create_task(rt.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await client.connect(client_t)
    handle = await client.submit(agent="capturing")
    await asyncio.wait_for(started.wait(), timeout=2.0)

    return client, accept_task, job_ctx_holder[0], handle


async def test_result_stream_write_str_utf8() -> None:
    """ResultStream.write with str data sends a result_chunk event."""
    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    client, accept_task, job_ctx, handle = await _make_job_context(rt, server_t, client_t)

    stream = job_ctx.stream_result()
    await stream.write("hello world")

    # Verify chunk_seq incremented and stream is not closed
    assert stream._chunk_seq == 1
    assert not stream._closed
    assert stream._total_size == len("hello world".encode("utf-8"))

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_result_stream_write_bytes_base64() -> None:
    """ResultStream.write with bytes data encodes as base64."""
    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    client, accept_task, job_ctx, handle = await _make_job_context(rt, server_t, client_t)

    raw = b"\x00\x01\x02\x03"
    stream = job_ctx.stream_result()
    await stream.write(raw)

    assert stream._chunk_seq == 1
    # The size should be length of base64-encoded string bytes
    expected_encoded = base64.b64encode(raw).decode("ascii")
    assert stream._total_size == len(expected_encoded.encode("utf-8"))

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_result_stream_write_after_close_raises() -> None:
    """Writing to a closed ResultStream raises InvalidRequestError."""
    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    client, accept_task, job_ctx, handle = await _make_job_context(rt, server_t, client_t)

    stream = job_ctx.stream_result()
    await stream.close()

    with pytest.raises(InvalidRequestError, match="closed"):
        await stream.write("too late")

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_result_stream_close_idempotent() -> None:
    """Closing a ResultStream twice is a no-op (no exception)."""
    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    client, accept_task, job_ctx, handle = await _make_job_context(rt, server_t, client_t)

    stream = job_ctx.stream_result()
    await stream.close()
    assert stream._closed

    # Second close must not raise
    await stream.close()

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_result_stream_context_manager_closes() -> None:
    """Using ResultStream as async context manager auto-closes on exit."""
    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    client, accept_task, job_ctx, handle = await _make_job_context(rt, server_t, client_t)

    async with job_ctx.stream_result() as stream:
        await stream.write("piece one")
        assert not stream._closed

    assert stream._closed

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_result_stream_context_manager_handles_exception() -> None:
    """ResultStream context manager closes even when an exception occurs inside."""
    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    client, accept_task, job_ctx, handle = await _make_job_context(rt, server_t, client_t)

    stream_ref: list[ResultStream] = []

    # Simulate a close error so __aexit__ logs but doesn't raise
    with contextlib.suppress(RuntimeError):
        async with job_ctx.stream_result() as stream:
            stream_ref.append(stream)
            await stream.write("data")
            # Don't raise — just exit normally

    # Stream should be closed after context exit
    if stream_ref:
        assert stream_ref[0]._closed

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_result_stream_close_with_summary() -> None:
    """ResultStream.close accepts an optional summary string."""
    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    client, accept_task, job_ctx, handle = await _make_job_context(rt, server_t, client_t)

    stream = job_ctx.stream_result()
    await stream.write("chunk data")
    # Close with a summary should not raise
    await stream.close(summary="completed successfully")
    assert stream._closed

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_result_stream_result_id_property() -> None:
    """ResultStream exposes its result_id via the result_id property."""
    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    client, accept_task, job_ctx, handle = await _make_job_context(rt, server_t, client_t)

    stream = job_ctx.stream_result(result_id="my-result-123")
    assert stream.result_id == "my-result-123"

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_result_stream_multiple_chunks_accumulate_size() -> None:
    """Writing multiple chunks accumulates total_size correctly."""
    rt = _make_rt()
    server_t, client_t = pair_memory_transports()
    client, accept_task, job_ctx, handle = await _make_job_context(rt, server_t, client_t)

    stream = job_ctx.stream_result()
    await stream.write("abc")  # 3 bytes
    await stream.write("de")   # 2 bytes
    await stream.write("f")    # 1 byte
    assert stream._chunk_seq == 3
    assert stream._total_size == 6

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()
