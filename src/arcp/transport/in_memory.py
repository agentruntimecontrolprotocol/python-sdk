"""In-memory transport pair for tests.

Two paired :class:`InMemoryTransport` instances form a bidirectional channel.
``server_side`` reads from the queue that ``client_side`` writes to, and vice
versa. The pair always preserves message bodies verbatim (round-tripping
through Pydantic serialization is the responsibility of higher layers).
"""

from __future__ import annotations

import asyncio
from typing import Any, override

from arcp.transport.base import Transport, TransportClosed


class InMemoryTransport(Transport):
    """In memory transport."""

    def __init__(
        self,
        outbound: asyncio.Queue[dict[str, Any] | None],
        inbound: asyncio.Queue[dict[str, Any] | None],
    ) -> None:
        self._outbound = outbound
        self._inbound = inbound
        self._closed = False

    @override
    async def send(self, envelope: dict[str, Any]) -> None:
        """Send."""
        if self._closed:
            raise TransportClosed("transport is closed")
        await self._outbound.put(envelope)

    @override
    async def recv(self) -> dict[str, Any]:
        """Recv."""
        item = await self._inbound.get()
        if item is None:
            raise TransportClosed("transport closed by peer")
        return item

    @override
    async def close(self) -> None:
        """Close."""
        if self._closed:
            return
        self._closed = True
        # Signal EOF to peer's recv() loop.
        await self._outbound.put(None)

    @property
    @override
    def is_closed(self) -> bool:
        """Is closed."""
        return self._closed


def create_pair() -> tuple[InMemoryTransport, InMemoryTransport]:
    """Return ``(client_side, server_side)`` paired transports."""
    a_to_b: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    b_to_a: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    client = InMemoryTransport(outbound=a_to_b, inbound=b_to_a)
    server = InMemoryTransport(outbound=b_to_a, inbound=a_to_b)
    return client, server


__all__ = ["InMemoryTransport", "create_pair"]
