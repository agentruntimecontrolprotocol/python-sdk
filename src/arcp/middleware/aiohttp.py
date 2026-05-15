"""aiohttp WebSocket adapter."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from .._transport.base import TransportClosed


class _AiohttpTransport:
    """Wrap an `aiohttp.web.WebSocketResponse` as a `Transport`."""

    def __init__(self, ws: Any) -> None:
        self._ws = ws
        self._closed = False
        self._iter = ws.__aiter__()

    async def send(self, envelope: dict[str, Any]) -> None:
        if self._closed:
            raise TransportClosed("transport closed")
        await self._ws.send_str(json.dumps(envelope, separators=(",", ":")))

    async def recv(self) -> dict[str, Any]:
        if self._closed:
            raise TransportClosed("transport closed")
        try:
            msg = await self._iter.__anext__()
        except StopAsyncIteration as e:
            self._closed = True
            raise TransportClosed("peer disconnected") from e
        # Late import to avoid hard aiohttp dep at module import time.
        from aiohttp import WSMsgType

        if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
            self._closed = True
            raise TransportClosed(f"ws msg type: {msg.type}")
        if msg.type != WSMsgType.TEXT:
            raise TransportClosed(f"unexpected ws msg type: {msg.type}")
        try:
            parsed = json.loads(msg.data)
        except json.JSONDecodeError as e:
            raise TransportClosed(f"malformed JSON frame: {e}") from e
        if not isinstance(parsed, dict):
            raise TransportClosed("expected JSON object frame")
        return parsed

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(Exception):
            await self._ws.close()

    @property
    def is_closed(self) -> bool:
        return self._closed


def arcp_aiohttp_handler(
    runtime: Any, *, allowed_hosts: Sequence[str] | None = None
) -> Callable[[Any], Awaitable[Any]]:
    """Return an aiohttp request handler that upgrades to WS and serves ARCP."""
    from aiohttp import web

    async def handler(request: Any) -> Any:
        if allowed_hosts is not None:
            host_header = request.headers.get("Host", "")
            host_only = host_header.split(":", 1)[0]
            if host_only not in allowed_hosts:
                return web.Response(status=403, text="Forbidden: Host header not allowed")
        ws = web.WebSocketResponse(heartbeat=None)
        await ws.prepare(request)
        transport = _AiohttpTransport(ws)
        try:
            await runtime.accept(transport)
        finally:
            await transport.close()
        return ws

    return handler


async def serve_arcp_aiohttp(
    runtime: Any,
    *,
    host: str = "127.0.0.1",
    port: int = 7777,
    path: str = "/arcp",
    allowed_hosts: Sequence[str] | None = None,
) -> Any:
    """Run a one-line aiohttp.web server hosting ARCP at `path`. Returns the runner."""
    from aiohttp import web

    app = web.Application()
    app.router.add_get(path, arcp_aiohttp_handler(runtime, allowed_hosts=allowed_hosts))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    return runner


__all__ = ("arcp_aiohttp_handler", "serve_arcp_aiohttp")
