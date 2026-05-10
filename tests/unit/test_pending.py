"""Unit tests for arcp.runtime.pending.PendingRequestRegistry."""

from __future__ import annotations

import asyncio

import pytest

from arcp.runtime.pending import PendingRequestRegistry


async def test_register_resolve_round_trip() -> None:
    reg = PendingRequestRegistry()
    fut = reg.register("c1")
    assert reg.resolve("c1", {"v": 1}) is True
    assert await fut == {"v": 1}


async def test_register_duplicate_raises() -> None:
    reg = PendingRequestRegistry()
    reg.register("c1")
    with pytest.raises(ValueError, match="duplicate pending correlation_id"):
        reg.register("c1")


async def test_resolve_unknown_returns_false() -> None:
    reg = PendingRequestRegistry()
    assert reg.resolve("nope", {}) is False


async def test_resolve_done_future_returns_false() -> None:
    reg = PendingRequestRegistry()
    reg.register("c1")
    assert reg.resolve("c1", {}) is True
    # second resolve finds nothing pending
    assert reg.resolve("c1", {}) is False


async def test_reject_propagates_exception() -> None:
    reg = PendingRequestRegistry()
    fut = reg.register("c1")
    err = RuntimeError("boom")
    assert reg.reject("c1", err) is True
    with pytest.raises(RuntimeError, match="boom"):
        await fut


async def test_reject_unknown_returns_false() -> None:
    reg = PendingRequestRegistry()
    assert reg.reject("missing", RuntimeError()) is False


async def test_cancel_marks_future_cancelled() -> None:
    reg = PendingRequestRegistry()
    fut = reg.register("c1")
    assert reg.cancel("c1") is True
    with pytest.raises(asyncio.CancelledError):
        await fut


async def test_cancel_unknown_returns_false() -> None:
    reg = PendingRequestRegistry()
    assert reg.cancel("missing") is False


async def test_cancel_all_clears_all_pending() -> None:
    reg = PendingRequestRegistry()
    f1 = reg.register("c1")
    f2 = reg.register("c2")
    reg.cancel_all()
    assert f1.cancelled()
    assert f2.cancelled()
    # registry is empty after cancel_all
    assert reg.resolve("c1", {}) is False
    assert reg.resolve("c2", {}) is False
