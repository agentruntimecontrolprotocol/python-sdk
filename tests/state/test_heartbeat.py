"""§6.4 heartbeat_loop — ping cycle, cancellation, and loss detection coverage."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
from unittest.mock import MagicMock

import pytest

from arcp._errors import HeartbeatLostError
from arcp._runtime.session import SessionContext, SessionState, heartbeat_loop
from arcp._transport.base import Transport


def _make_ctx() -> SessionContext:
    """Construct a minimal SessionContext for heartbeat testing."""
    state = SessionState(
        session_id="heartbeat-test-session",
        resume_token="tok",
        principal="p1",
        negotiated_features=(),
        heartbeat_interval_sec=None,
        resume_window_sec=60,
        accepted_at=dt.datetime.now(dt.UTC),
    )
    transport = MagicMock(spec=Transport)
    return SessionContext(
        transport=transport,
        state=state,
        send_queue=asyncio.Queue(),
    )


async def test_heartbeat_cancelled_returns_cleanly() -> None:
    """CancelledError during sleep causes heartbeat_loop to exit without setting exception."""
    ctx = _make_ctx()
    loop = asyncio.get_running_loop()
    ctx.heartbeat_outcome = loop.create_future()

    task = asyncio.create_task(heartbeat_loop(ctx, interval=60.0))
    await asyncio.sleep(0.01)  # let the task enter asyncio.sleep
    task.cancel()

    with contextlib.suppress(asyncio.CancelledError):
        await task

    # heartbeat_outcome must not have been set
    assert not ctx.heartbeat_outcome.done()
    ctx.heartbeat_outcome.cancel()  # clean up the future


async def test_heartbeat_lost_sets_exception_on_outcome() -> None:
    """Gap >= interval * miss_threshold raises and sets HeartbeatLostError on outcome."""
    ctx = _make_ctx()
    loop = asyncio.get_running_loop()
    ctx.heartbeat_outcome = loop.create_future()

    # Back-date last_inbound_at so gap is always enormous
    ctx._last_inbound_at = dt.datetime(2000, 1, 1, tzinfo=dt.UTC)

    # interval=0.05 s, miss_threshold=1 → threshold=0.05 s; gap >> threshold
    with pytest.raises(HeartbeatLostError):
        await asyncio.wait_for(
            heartbeat_loop(ctx, interval=0.05, miss_threshold=1),
            timeout=1.0,
        )

    # The outcome future is also resolved with the same error for waiters
    assert ctx.heartbeat_outcome.done()
    with pytest.raises(HeartbeatLostError):
        ctx.heartbeat_outcome.result()


async def test_heartbeat_loss_without_outcome_future_is_safe() -> None:
    """heartbeat_loop raises HeartbeatLostError even when no outcome future is attached."""
    ctx = _make_ctx()
    ctx.heartbeat_outcome = None  # no future attached

    # Back-date to trigger loss on first check
    ctx._last_inbound_at = dt.datetime(2000, 1, 1, tzinfo=dt.UTC)

    with pytest.raises(HeartbeatLostError):
        await asyncio.wait_for(
            heartbeat_loop(ctx, interval=0.05, miss_threshold=1),
            timeout=1.0,
        )


async def test_heartbeat_sends_ping_and_invokes_on_ping_callback() -> None:
    """Normal interval enqueues session.ping and calls on_ping with the nonce."""
    ctx = _make_ctx()
    received_nonces: list[str] = []

    # Use large miss_threshold so we never trigger the lost-heartbeat branch
    task = asyncio.create_task(
        heartbeat_loop(ctx, interval=0.05, miss_threshold=20, on_ping=received_nonces.append)
    )
    # Wait long enough for at least one complete iteration
    await asyncio.sleep(0.13)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert len(received_nonces) >= 1

    # The send queue must contain at least one session.ping envelope
    found_ping = False
    while not ctx._send_queue.empty():
        item = ctx._send_queue.get_nowait()
        if item is not None and item.type == "session.ping":
            found_ping = True
            break
    assert found_ping, "expected at least one session.ping in the send queue"


async def test_heartbeat_loss_with_done_outcome_does_not_raise_invalid_state() -> None:
    """If heartbeat_outcome is already done, set_exception is skipped (guarded by .done())."""
    ctx = _make_ctx()
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[None] = loop.create_future()
    fut.cancel()  # mark future as done (cancelled)
    ctx.heartbeat_outcome = fut

    ctx._last_inbound_at = dt.datetime(2000, 1, 1, tzinfo=dt.UTC)

    # Should raise HeartbeatLostError without InvalidStateError on the done future.
    with pytest.raises(HeartbeatLostError):
        await asyncio.wait_for(
            heartbeat_loop(ctx, interval=0.05, miss_threshold=1),
            timeout=1.0,
        )
