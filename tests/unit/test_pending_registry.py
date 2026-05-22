"""Unit tests for arcp._runtime.pending.PendingRegistry."""

from __future__ import annotations

import pytest

from arcp._runtime.pending import PendingRegistry


async def test_register_and_resolve() -> None:
    reg = PendingRegistry()
    fut = reg.register("req-1")
    resolved = reg.resolve("req-1", {"value": 42})
    assert resolved is True
    assert fut.result() == {"value": 42}


async def test_resolve_unknown_returns_false() -> None:
    reg = PendingRegistry()
    assert reg.resolve("nonexistent", "value") is False


async def test_reject_sets_exception() -> None:
    reg = PendingRegistry()
    fut = reg.register("req-2")
    err = ValueError("oops")
    rejected = reg.reject("req-2", err)
    assert rejected is True
    with pytest.raises(ValueError, match="oops"):
        fut.result()


async def test_reject_unknown_returns_false() -> None:
    reg = PendingRegistry()
    assert reg.reject("nonexistent", ValueError("x")) is False


async def test_reject_already_done_returns_false() -> None:
    reg = PendingRegistry()
    fut = reg.register("req-3")
    reg.resolve("req-3", "first")
    # Future is already popped and done; reject the same key again
    result = reg.reject("req-3", ValueError("late"))
    assert result is False
    # Original future still holds the first result
    assert fut.result() == "first"


async def test_cancel_all_sets_exception_on_all() -> None:
    reg = PendingRegistry()
    f1 = reg.register("a")
    f2 = reg.register("b")
    exc = RuntimeError("session closed")
    reg.cancel_all(exc)
    for fut in (f1, f2):
        assert fut.done()
        with pytest.raises(RuntimeError, match="session closed"):
            fut.result()


async def test_cancel_all_clears_registry() -> None:
    reg = PendingRegistry()
    reg.register("x")
    reg.cancel_all(Exception("done"))
    # After cancel_all, resolving any key should be a no-op (not in registry)
    assert reg.resolve("x", "late") is False
