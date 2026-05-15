"""In-memory paired-queue transport, the canonical test seam."""

from __future__ import annotations

import asyncio
from typing import Any

from .base import TransportClosed


class MemoryTransport:
    """One half of a paired in-memory transport. `recv` reads from `inbox`."""

    def __init__(
        self,
        inbox: asyncio.Queue[dict[str, Any] | None],
        outbox: asyncio.Queue[dict[str, Any] | None],
    ) -> None:
        self._inbox = inbox
        self._outbox = outbox
        self._closed = False

    async def send(self, envelope: dict[str, Any]) -> None:
        if self._closed:
            raise TransportClosed("transport closed")
        await self._outbox.put(envelope)

    async def recv(self) -> dict[str, Any]:
        if self._closed:
            raise TransportClosed("transport closed")
        item = await self._inbox.get()
        if item is None:
            self._closed = True
            raise TransportClosed("peer closed")
        return item

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._outbox.put(None)

    @property
    def is_closed(self) -> bool:
        return self._closed


def pair_memory_transports() -> tuple[MemoryTransport, MemoryTransport]:
    """Return two `MemoryTransport`s connected to each other."""
    a_to_b: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    b_to_a: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    a = MemoryTransport(inbox=b_to_a, outbox=a_to_b)
    b = MemoryTransport(inbox=a_to_b, outbox=b_to_a)
    return a, b


__all__ = ("MemoryTransport", "pair_memory_transports")
