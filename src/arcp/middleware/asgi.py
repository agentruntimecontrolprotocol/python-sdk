"""ASGI 3 WebSocket adapter for any ASGI app (Starlette/FastAPI/Litestar/Quart)."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, cast

from .._transport.base import TransportClosed

ASGIScope = dict[str, Any]
ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]


class _ASGITransport:
    """Wrap an accepted ASGI WebSocket scope as a `Transport`."""

    def __init__(self, receive: ASGIReceive, send: ASGISend) -> None:
        self._receive = receive
        self._send = send
        self._closed = False

    async def send(self, envelope: dict[str, Any]) -> None:
        if self._closed:
            raise TransportClosed("transport closed")
        await self._send(
            {"type": "websocket.send", "text": json.dumps(envelope, separators=(",", ":"))}
        )

    async def recv(self) -> dict[str, Any]:
        if self._closed:
            raise TransportClosed("transport closed")
        event = await self._receive()
        et = event.get("type")
        if et == "websocket.disconnect":
            self._closed = True
            raise TransportClosed("peer disconnected")
        if et != "websocket.receive":
            raise TransportClosed(f"unexpected ASGI event: {et!r}")
        text = event.get("text")
        if text is None:
            raw = event.get("bytes", b"") or b""
            text = raw.decode("utf-8")
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
        with contextlib.suppress(Exception):
            await self._send({"type": "websocket.close", "code": 1000})

    @property
    def is_closed(self) -> bool:
        return self._closed


def _host_allowed(scope: ASGIScope, allowed: Sequence[str] | None) -> bool:
    if allowed is None:
        return True
    headers = scope.get("headers", [])
    host_value = ""
    for k, v in headers:
        if k == b"host":
            host_value = v.decode("latin-1")
            break
    host_only = host_value.split(":", 1)[0]
    return host_only in allowed


def arcp_asgi_app(runtime: Any, *, allowed_hosts: Sequence[str] | None = None) -> ASGIApp:
    """Return an ASGI 3 callable mounting ARCP on the host app's WS route."""

    async def app(scope: ASGIScope, receive: ASGIReceive, send: ASGISend) -> None:
        if scope.get("type") != "websocket":
            raise ValueError("arcp_asgi_app expects an ASGI websocket scope")
        if not _host_allowed(scope, allowed_hosts):
            await send({"type": "websocket.close", "code": 1008})
            return
        # Wait for connect, then accept.
        connect = await receive()
        if connect.get("type") != "websocket.connect":
            await send({"type": "websocket.close", "code": 1011})
            return
        await send({"type": "websocket.accept"})
        transport = _ASGITransport(receive, send)
        try:
            await runtime.accept(transport)
        finally:
            await transport.close()

    return app


__all__ = ("arcp_asgi_app",)
