"""WebSocket transport (client + server primitives) backed by the `websockets` library."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, cast

from websockets.asyncio.client import ClientConnection, connect
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .base import TransportClosed


class WebSocketTransport:
    """Wraps a `websockets` connection (client- or server-side) as a `Transport`."""

    def __init__(self, conn: ClientConnection | ServerConnection) -> None:
        self._conn = conn
        self._closed = False

    async def send(self, envelope: dict[str, Any]) -> None:
        if self._closed:
            raise TransportClosed("transport closed")
        try:
            await self._conn.send(json.dumps(envelope, separators=(",", ":")))
        except ConnectionClosed as e:
            self._closed = True
            raise TransportClosed(str(e)) from e

    async def recv(self) -> dict[str, Any]:
        if self._closed:
            raise TransportClosed("transport closed")
        try:
            msg = await self._conn.recv()
        except ConnectionClosed as e:
            self._closed = True
            raise TransportClosed(str(e)) from e
        text = msg.decode("utf-8") if isinstance(msg, bytes) else msg
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise TransportClosed(f"malformed JSON frame: {e}") from e
        if not isinstance(parsed, dict):
            raise TransportClosed("expected JSON object frame")
        return cast(dict[str, Any], parsed)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(ConnectionClosed, OSError):
            await self._conn.close()

    @property
    def is_closed(self) -> bool:
        return self._closed

    def write_buffer_size(self) -> int | None:
        """Best-effort access to the underlying socket write buffer (for §6.5 backpressure)."""
        try:
            transport = getattr(self._conn, "transport", None)
            if transport is None:
                return None
            size = transport.get_write_buffer_size()
        except (AttributeError, OSError):
            return None
        return int(size) if size is not None else None

    @classmethod
    async def connect(cls, url: str, **kwargs: Any) -> WebSocketTransport:
        """Open a client WebSocket connection to `url`."""
        conn = await connect(url, **kwargs)
        return cls(conn)


async def serve_websocket(
    on_transport: Callable[[WebSocketTransport], Awaitable[None]],
    *,
    host: str,
    port: int,
    path: str = "/arcp",
    allowed_hosts: tuple[str, ...] | None = None,
    **kwargs: Any,
) -> Server:
    """Start a `websockets` server; calls `on_transport` for each accepted connection."""

    async def handler(conn: ServerConnection) -> None:
        request = conn.request
        if path and request is not None and request.path != path:
            await conn.close(code=1008, reason="path not allowed")
            return
        if allowed_hosts is not None:
            host_header = ""
            if request is not None:
                host_header = request.headers.get("Host", "")
            host_only = host_header.split(":", 1)[0]
            if host_only not in allowed_hosts:
                await conn.close(code=1008, reason="host not allowed")
                return
        transport = WebSocketTransport(conn)
        try:
            await on_transport(transport)
        finally:
            await transport.close()

    server = await serve(handler, host=host, port=port, **kwargs)
    # Cooperate with linters and asyncio: keep a small await to ensure the server is
    # actually accepting before we return.
    await asyncio.sleep(0)
    return server


__all__ = ("WebSocketTransport", "serve_websocket")
