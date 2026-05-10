"""Bidirectional correlation registry (RFC §6.3).

Maps ``correlation_id`` → :class:`asyncio.Future` so that request envelopes can
await their paired response envelope. Used by ``permission.request``,
``human.input.request``, and ``human.choice.request``.
"""

from __future__ import annotations

import asyncio
from typing import Any


class PendingRequestRegistry:
    """Per-session correlation table."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}

    def register(self, correlation_id: str) -> asyncio.Future[dict[str, Any]]:
        """Register and return a pending future keyed by ``correlation_id``."""
        if correlation_id in self._pending:
            raise ValueError(f"duplicate pending correlation_id: {correlation_id}")
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[correlation_id] = future
        return future

    def resolve(self, correlation_id: str, response: dict[str, Any]) -> bool:
        """Resolve the pending future. Returns ``False`` if no entry."""
        future = self._pending.pop(correlation_id, None)
        if future is None or future.done():
            return False
        future.set_result(response)
        return True

    def reject(self, correlation_id: str, error: BaseException) -> bool:
        """Fail the pending future. Returns ``False`` if no entry."""
        future = self._pending.pop(correlation_id, None)
        if future is None or future.done():
            return False
        future.set_exception(error)
        return True

    def cancel(self, correlation_id: str) -> bool:
        """Cancel."""
        future = self._pending.pop(correlation_id, None)
        if future is None or future.done():
            return False
        future.cancel()
        return True

    def cancel_all(self) -> None:
        """Cancel all."""
        for cid in list(self._pending):
            self.cancel(cid)


__all__ = ["PendingRequestRegistry"]
