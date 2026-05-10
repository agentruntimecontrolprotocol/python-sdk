"""WebSocket transport (RFC §22).

Each WebSocket connection corresponds to a single ARCP session. The transport
preserves message body and delivery contract; framing is one envelope per
text frame, JSON-encoded.
"""

from __future__ import annotations

import json
from typing import Any, cast, override

import websockets
from websockets.asyncio.client import ClientConnection, connect
from websockets.asyncio.server import ServerConnection
from websockets.asyncio.server import serve as ws_serve

from arcp.transport.base import Transport, TransportClosed


class WebSocketTransport(Transport):
    """Wraps a connected WebSocket (server- or client-side)."""

    def __init__(self, ws: ServerConnection | ClientConnection) -> None:
        self._ws = ws
        self._closed = False

    @override
    async def send(self, envelope: dict[str, Any]) -> None:
        if self._closed:
            raise TransportClosed("transport is closed")
        try:
            await self._ws.send(json.dumps(envelope))
        except websockets.ConnectionClosed as exc:
            self._closed = True
            raise TransportClosed("websocket closed") from exc

    @override
    async def recv(self) -> dict[str, Any]:
        try:
            raw = await self._ws.recv()
        except websockets.ConnectionClosed as exc:
            self._closed = True
            raise TransportClosed("websocket closed") from exc
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        parsed = json.loads(raw)
        return cast("dict[str, Any]", parsed)

    @override
    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._ws.close()
        except Exception:
            pass

    @property
    @override
    def is_closed(self) -> bool:
        return self._closed


async def connect_websocket(uri: str) -> WebSocketTransport:
    """Connect to ``uri`` (e.g. ``ws://localhost:7777``) and wrap in a transport."""

    ws = await connect(uri)
    return WebSocketTransport(ws)


# Re-export ws_serve and ServerConnection so callers can spin up servers without a
# separate import.
__all__ = ["ServerConnection", "WebSocketTransport", "connect_websocket", "ws_serve"]
