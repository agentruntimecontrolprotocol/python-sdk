"""Newline-delimited JSON over stdin/stdout per spec §4.2."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, cast

from .base import TransportClosed


class StdioTransport:
    """Read NDJSON envelopes from a `StreamReader`; write to a `StreamWriter`."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer
        self._closed = False
        self._send_lock = asyncio.Lock()

    async def send(self, envelope: dict[str, Any]) -> None:
        if self._closed:
            raise TransportClosed("transport closed")
        line = (json.dumps(envelope, separators=(",", ":")) + "\n").encode("utf-8")
        async with self._send_lock:
            self._writer.write(line)
            await self._writer.drain()

    async def recv(self) -> dict[str, Any]:
        if self._closed:
            raise TransportClosed("transport closed")
        line = await self._reader.readline()
        if not line:
            self._closed = True
            raise TransportClosed("peer closed stdin")
        try:
            parsed = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise TransportClosed(f"malformed NDJSON: {e}") from e
        if not isinstance(parsed, dict):
            raise TransportClosed("expected JSON object frame")
        return cast(dict[str, Any], parsed)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass

    @property
    def is_closed(self) -> bool:
        return self._closed

    @classmethod
    async def from_process_pipes(cls, proc: asyncio.subprocess.Process) -> StdioTransport:
        """Wrap a subprocess's stdout (read) and stdin (write) as a transport."""
        if proc.stdout is None or proc.stdin is None:
            raise ValueError("subprocess must be created with stdin and stdout pipes")
        return cls(reader=proc.stdout, writer=proc.stdin)

    @classmethod
    async def from_std_streams(cls) -> StdioTransport:
        """Wrap the current process's stdin/stdout as a transport."""
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        write_transport, write_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(write_transport, write_protocol, reader=None, loop=loop)
        return cls(reader=reader, writer=writer)


__all__ = ("StdioTransport",)
