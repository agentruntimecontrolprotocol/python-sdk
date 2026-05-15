"""Pending request registry: correlate request envelope `id` to a Future of the response."""

from __future__ import annotations

import asyncio
from typing import Any


class PendingRegistry:
    """Map envelope `id` to an `asyncio.Future` resolved when the matching reply arrives."""

    def __init__(self) -> None:
        self._waiters: dict[str, asyncio.Future[Any]] = {}

    def register(self, request_id: str) -> asyncio.Future[Any]:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._waiters[request_id] = fut
        return fut

    def resolve(self, request_id: str, value: Any) -> bool:
        fut = self._waiters.pop(request_id, None)
        if fut is None or fut.done():
            return False
        fut.set_result(value)
        return True

    def reject(self, request_id: str, exc: BaseException) -> bool:
        fut = self._waiters.pop(request_id, None)
        if fut is None or fut.done():
            return False
        fut.set_exception(exc)
        return True

    def cancel_all(self, exc: BaseException) -> None:
        for fut in list(self._waiters.values()):
            if not fut.done():
                fut.set_exception(exc)
        self._waiters.clear()


__all__ = ("PendingRegistry",)
