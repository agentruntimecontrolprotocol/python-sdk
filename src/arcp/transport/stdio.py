"""stdio transport (RFC §22).

Newline-delimited JSON over an :class:`asyncio.StreamReader`/``StreamWriter`` pair.
Used for shim integrations and subprocess-based tests.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, cast, override

from arcp.transport.base import Transport, TransportClosed


class StdioTransport(Transport):
    """Newline-delimited JSON over a reader/writer pair."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer
        self._closed = False

    @override
    async def send(self, envelope: dict[str, Any]) -> None:
        if self._closed:
            raise TransportClosed("transport is closed")
        line = json.dumps(envelope, separators=(",", ":")) + "\n"
        self._writer.write(line.encode("utf-8"))
        await self._writer.drain()

    @override
    async def recv(self) -> dict[str, Any]:
        line = await self._reader.readline()
        if not line:
            self._closed = True
            raise TransportClosed("stdio reader at EOF")
        parsed = json.loads(line.decode("utf-8"))
        return cast("dict[str, Any]", parsed)

    @override
    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.close()
        except Exception:
            pass

    @property
    @override
    def is_closed(self) -> bool:
        return self._closed


async def connect_stdio_pipe() -> StdioTransport:
    """Wrap ``sys.stdin``/``sys.stdout`` as a transport.

    Reads lines from stdin and writes lines to stdout. Useful for subprocess
    integration where the parent runtime spawns a child agent.
    """

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    write_transport, write_proto = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(write_transport, write_proto, None, loop)
    return StdioTransport(reader, writer)


__all__ = ["StdioTransport", "connect_stdio_pipe"]
