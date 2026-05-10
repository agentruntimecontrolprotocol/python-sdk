"""Tests for the SQLite event log (RFC §6.4, §13.3, §19)."""

from __future__ import annotations

import pytest

from arcp.envelope import Envelope
from arcp.store.eventlog import EventLog


def _env(message_id: str, **overrides: object) -> Envelope:
    base: dict[str, object] = {
        "id": message_id,
        "type": "log",
        "session_id": "sess_a",
        "timestamp": "2026-05-09T13:00:00Z",
    }
    base.update(overrides)
    return Envelope.model_validate(base)


@pytest.mark.asyncio
async def test_append_and_replay_roundtrips_envelope() -> None:
    async with EventLog(":memory:") as log:
        original = _env("m1", trace_id="t1")
        assert await log.append(original) is True
        results = [e async for e in log.replay(session_id="sess_a")]
        assert len(results) == 1
        assert results[0].id == "m1"
        assert results[0].trace_id == "t1"


@pytest.mark.asyncio
async def test_append_dedups_on_message_id() -> None:
    async with EventLog(":memory:") as log:
        await log.append(_env("m1"))
        # Re-append same id; should be a no-op (returns False).
        assert await log.append(_env("m1", type="log")) is False
        count = 0
        async for _ in log.replay(session_id="sess_a"):
            count += 1
        assert count == 1


@pytest.mark.asyncio
async def test_replay_preserves_insert_order_across_sessions() -> None:
    async with EventLog(":memory:") as log:
        for i in range(5):
            await log.append(_env(f"m{i}", session_id="sess_a"))
        for i in range(5):
            await log.append(_env(f"n{i}", session_id="sess_b"))
        sess_a_ids = [e.id async for e in log.replay(session_id="sess_a")]
        sess_b_ids = [e.id async for e in log.replay(session_id="sess_b")]
        assert sess_a_ids == [f"m{i}" for i in range(5)]
        assert sess_b_ids == [f"n{i}" for i in range(5)]


@pytest.mark.asyncio
async def test_replay_after_message_id_skips_anchor() -> None:
    async with EventLog(":memory:") as log:
        for i in range(5):
            await log.append(_env(f"m{i}"))
        ids = [e.id async for e in log.replay(session_id="sess_a", after_message_id="m2")]
        assert ids == ["m3", "m4"]


@pytest.mark.asyncio
async def test_replay_after_unknown_anchor_returns_empty() -> None:
    async with EventLog(":memory:") as log:
        await log.append(_env("m0"))
        ids = [e.id async for e in log.replay(session_id="sess_a", after_message_id="missing")]
        assert ids == []


@pytest.mark.asyncio
async def test_has_message() -> None:
    async with EventLog(":memory:") as log:
        await log.append(_env("m1"))
        assert await log.has_message(session_id="sess_a", message_id="m1") is True
        assert await log.has_message(session_id="sess_a", message_id="missing") is False


@pytest.mark.asyncio
async def test_idempotency_results_store_and_lookup() -> None:
    async with EventLog(":memory:") as log:
        result = {"type": "tool.result", "payload": {"ok": True}}
        assert await log.remember_idempotent(
            principal="alice",
            idempotency_key="k1",
            result=result,
            created_at="2026-05-09T13:00:00Z",
        ) is True
        # Repeat is a no-op.
        assert await log.remember_idempotent(
            principal="alice",
            idempotency_key="k1",
            result={"different": True},
            created_at="2026-05-09T13:00:01Z",
        ) is False
        stored = await log.lookup_idempotent(principal="alice", idempotency_key="k1")
        assert stored == result
        # Different principal sees nothing.
        assert await log.lookup_idempotent(principal="bob", idempotency_key="k1") is None


@pytest.mark.asyncio
async def test_gc_before_removes_old_events() -> None:
    async with EventLog(":memory:") as log:
        await log.append(_env("old", timestamp="2025-01-01T00:00:00Z"))
        await log.append(_env("new", timestamp="2026-05-09T13:00:00Z"))
        deleted = await log.gc_before("2026-01-01T00:00:00Z")
        assert deleted == 1
        ids = [e.id async for e in log.replay(session_id="sess_a")]
        assert ids == ["new"]
