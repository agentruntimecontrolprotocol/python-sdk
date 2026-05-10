"""Abstract transport interface (RFC §22).

Transports preserve message body and delivery contract. The runtime and
client both work against this abstract interface; concrete transports
(``websocket``, ``stdio``, ``in_memory``) live in sibling modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TransportClosed(Exception):  # noqa: N818 — protocol-style state name, not an "error".
    """Raised when ``recv`` is called on a closed transport."""


class Transport(ABC):
    """Bidirectional, message-framed transport."""

    @abstractmethod
    async def send(self, envelope: dict[str, Any]) -> None:
        """Send a single envelope (already serialized to a JSON-compatible dict)."""

    @abstractmethod
    async def recv(self) -> dict[str, Any]:
        """Receive the next envelope. Raises :class:`TransportClosed` at EOF."""

    @abstractmethod
    async def close(self) -> None:
        """Close the transport. Idempotent."""

    @property
    @abstractmethod
    def is_closed(self) -> bool:
        ...


__all__ = ["Transport", "TransportClosed"]
