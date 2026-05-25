"""Event log: in-memory by default, optionally backed by aiosqlite."""

from __future__ import annotations

import asyncio
import bisect
import json
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from importlib import resources
from pathlib import Path
from typing import Any, Protocol


class EventLog(Protocol):
    """Append seq-bearing envelopes; replay slices; release acked prefixes."""

    async def append(self, session_id: str, envelope: dict[str, Any]) -> None: ...
    def read_since_seq(self, session_id: str, after_seq: int) -> AsyncIterator[dict[str, Any]]: ...
    async def latest_seq(self, session_id: str) -> int: ...
    async def release_through(self, session_id: str, through_seq: int) -> None: ...
    async def drop_session(self, session_id: str) -> None: ...
    async def close(self) -> None: ...


class InMemoryEventLog:
    """Default implementation. Single-process, no persistence.

    Maintains per-session events in append-only seq order plus a parallel
    sorted seq array so `read_since_seq` and `release_through` use `bisect`
    rather than scanning the whole history.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        # Parallel array of event_seq values for bisect lookup. Always
        # monotonically non-decreasing because seqs are stamped in order.
        self._seqs: dict[str, list[int]] = defaultdict(list)
        self._released_through: dict[str, int] = defaultdict(int)

    async def append(self, session_id: str, envelope: dict[str, Any]) -> None:
        seq = envelope.get("event_seq")
        if not isinstance(seq, int):
            raise ValueError("envelope must carry event_seq to be appended")
        seqs = self._seqs[session_id]
        # Idempotent append: if this seq is already stored, ignore. Resume
        # replays send the same envelopes back through the write pump, and
        # the log MUST remain a faithful single-record-per-seq history.
        if seqs and seqs[-1] >= seq and seq in seqs:
            return
        self._events[session_id].append(dict(envelope))
        seqs.append(seq)

    async def read_since_seq(
        self, session_id: str, after_seq: int
    ) -> AsyncIterator[dict[str, Any]]:
        events = self._events.get(session_id)
        if not events:
            return
        seqs = self._seqs.get(session_id, ())
        start = bisect.bisect_right(seqs, after_seq)
        for env in events[start:]:
            yield env

    async def latest_seq(self, session_id: str) -> int:
        seqs = self._seqs.get(session_id, ())
        return seqs[-1] if seqs else 0

    async def release_through(self, session_id: str, through_seq: int) -> None:
        if through_seq <= self._released_through[session_id]:
            return
        self._released_through[session_id] = through_seq
        seqs = self._seqs.get(session_id)
        events = self._events.get(session_id)
        if not seqs or not events:
            return
        cut = bisect.bisect_right(seqs, through_seq)
        if cut == 0:
            return
        # Slice off the prefix instead of building a filtered copy.
        del seqs[:cut]
        del events[:cut]

    async def drop_session(self, session_id: str) -> None:
        self._events.pop(session_id, None)
        self._seqs.pop(session_id, None)
        self._released_through.pop(session_id, None)

    async def close(self) -> None:
        self._events.clear()
        self._seqs.clear()
        self._released_through.clear()


class SqliteEventLog:
    """Persistent event log on aiosqlite. Lazy-imported to avoid the dep at import time."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._db: Any = None
        self._open_lock = asyncio.Lock()

    async def _ensure_open(self) -> Any:
        # Fast path: already open, no lock contention.
        if self._db is not None:
            return self._db
        async with self._open_lock:
            # Re-check after acquiring the lock so a second concurrent
            # caller does not open a duplicate connection. The recheck is
            # the entire point of the lock; mypy/pyright can't model the
            # concurrent mutation of `self._db` here, so use getattr to
            # avoid an unreachable-branch warning.
            existing = self.__dict__.get("_db")
            if existing is not None:
                return existing
            import aiosqlite

            db = await aiosqlite.connect(self._path)
            schema = resources.files("arcp._store").joinpath("schema.sql").read_text()
            await db.executescript(schema)
            # WAL allows concurrent readers and writers; safe for our schema.
            await db.execute("PRAGMA journal_mode=WAL")
            await db.commit()
            self._db = db
            return self._db

    async def append(self, session_id: str, envelope: dict[str, Any]) -> None:
        seq = envelope.get("event_seq")
        if not isinstance(seq, int):
            raise ValueError("envelope must carry event_seq to be appended")
        db = await self._ensure_open()
        # `OR IGNORE` keeps the resume path idempotent: replays send the
        # same envelopes back through the write pump.
        await db.execute(
            "INSERT OR IGNORE INTO events "
            "(session_id, event_seq, job_id, type, envelope, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_id,
                seq,
                envelope.get("job_id"),
                envelope["type"],
                json.dumps(envelope, separators=(",", ":")),
                time.time(),
            ),
        )
        await db.commit()

    async def read_since_seq(
        self, session_id: str, after_seq: int
    ) -> AsyncIterator[dict[str, Any]]:
        db = await self._ensure_open()
        async with db.execute(
            "SELECT envelope FROM events WHERE session_id=? AND event_seq>? ORDER BY event_seq",
            (session_id, after_seq),
        ) as cur:
            async for row in cur:
                yield json.loads(row[0])

    async def latest_seq(self, session_id: str) -> int:
        db = await self._ensure_open()
        async with db.execute(
            "SELECT MAX(event_seq) FROM events WHERE session_id=?",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0

    async def release_through(self, session_id: str, through_seq: int) -> None:
        db = await self._ensure_open()
        await db.execute(
            "DELETE FROM events WHERE session_id=? AND event_seq<=?",
            (session_id, through_seq),
        )
        await db.commit()

    async def drop_session(self, session_id: str) -> None:
        db = await self._ensure_open()
        await db.execute("DELETE FROM events WHERE session_id=?", (session_id,))
        await db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None


__all__ = ("EventLog", "InMemoryEventLog", "SqliteEventLog")
