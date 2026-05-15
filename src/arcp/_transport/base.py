"""Transport protocol: send/recv/close on the wire-frame boundary (dict in / dict out)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class TransportClosed(Exception):
    """Raised on `recv` when the peer has closed; raised on `send` after close."""


@runtime_checkable
class Transport(Protocol):
    """Bidirectional, ordered, JSON-frame transport for a single ARCP session."""

    async def send(self, envelope: dict[str, Any]) -> None: ...
    async def recv(self) -> dict[str, Any]: ...
    async def close(self) -> None: ...

    @property
    def is_closed(self) -> bool: ...


__all__ = ("Transport", "TransportClosed")
