"""Unit tests for arcp.transport.stdio.StdioTransport (in-process pipes)."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from arcp.transport.base import TransportClosed
from arcp.transport.stdio import StdioTransport


async def _pipe_pair() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Build a connected reader/writer over an OS pipe usable on POSIX hosts."""
    loop = asyncio.get_running_loop()
    rfd, wfd = os.pipe()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, os.fdopen(rfd, "rb", buffering=0))
    write_transport, write_proto = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, os.fdopen(wfd, "wb", buffering=0)
    )
    writer = asyncio.StreamWriter(write_transport, write_proto, None, loop)
    return reader, writer


async def test_send_round_trips_one_envelope() -> None:
    reader, writer = await _pipe_pair()
    t = StdioTransport(reader, writer)
    await t.send({"hello": "world"})
    line = await reader.readline()
    assert json.loads(line) == {"hello": "world"}
    await t.close()


async def test_send_after_close_raises_transport_closed() -> None:
    _, writer = await _pipe_pair()
    # Build a reader that's never used; we only exercise the closed-on-send path.
    t = StdioTransport(asyncio.StreamReader(), writer)
    await t.close()
    assert t.is_closed
    with pytest.raises(TransportClosed):
        await t.send({"x": 1})


async def test_recv_at_eof_marks_closed_and_raises() -> None:
    reader, writer = await _pipe_pair()
    t = StdioTransport(reader, writer)
    # Closing the writer side delivers EOF to reader.
    writer.close()
    with pytest.raises(TransportClosed, match="EOF"):
        await t.recv()
    assert t.is_closed


async def test_close_is_idempotent() -> None:
    _, writer = await _pipe_pair()
    t = StdioTransport(asyncio.StreamReader(), writer)
    await t.close()
    await t.close()  # second call returns early
    assert t.is_closed


async def test_close_swallows_writer_close_failures() -> None:
    """If the underlying writer.close() raises, close() still marks closed."""

    class _BadWriter:
        def close(self) -> None:
            raise OSError("forced")

    t = StdioTransport(asyncio.StreamReader(), _BadWriter())  # type: ignore[arg-type]
    await t.close()
    assert t.is_closed
