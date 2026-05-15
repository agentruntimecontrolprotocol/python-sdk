"""Event log: in-memory by default, optionally backed by aiosqlite."""

from __future__ import annotations

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
    """Default implementation. Single-process, no persistence."""

    def __init__(self) -> None:
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._released_through: dict[str, int] = defaultdict(int)

    async def append(self, session_id: str, envelope: dict[str, Any]) -> None:
        seq = envelope.get("event_seq")
        if not isinstance(seq, int):
            raise ValueError("envelope must carry event_seq to be appended")
        self._events[session_id].append(dict(envelope))

    async def read_since_seq(
        self, session_id: str, after_seq: int
    ) -> AsyncIterator[dict[str, Any]]:
        for env in list(self._events.get(session_id, ())):
            if int(env["event_seq"]) > after_seq:
                yield env

    async def latest_seq(self, session_id: str) -> int:
        events = self._events.get(session_id, ())
        return int(events[-1]["event_seq"]) if events else 0

    async def release_through(self, session_id: str, through_seq: int) -> None:
        if through_seq <= self._released_through[session_id]:
            return
        self._released_through[session_id] = through_seq
        events = self._events.get(session_id)
        if not events:
            return
        self._events[session_id] = [e for e in events if int(e["event_seq"]) > through_seq]

    async def drop_session(self, session_id: str) -> None:
        self._events.pop(session_id, None)
        self._released_through.pop(session_id, None)

    async def close(self) -> None:
        self._events.clear()
        self._released_through.clear()


class SqliteEventLog:
    """Persistent event log on aiosqlite. Lazy-imported to avoid the dep at import time."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._db: Any = None

    async def _ensure_open(self) -> Any:
        if self._db is not None:
            return self._db
        import aiosqlite

        self._db = await aiosqlite.connect(self._path)
        schema = resources.files("arcp._store").joinpath("schema.sql").read_text()
        await self._db.executescript(schema)
        await self._db.commit()
        return self._db

    async def append(self, session_id: str, envelope: dict[str, Any]) -> None:
        seq = envelope.get("event_seq")
        if not isinstance(seq, int):
            raise ValueError("envelope must carry event_seq to be appended")
        db = await self._ensure_open()
        await db.execute(
            "INSERT INTO events (session_id, event_seq, job_id, type, envelope, created_at)"
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
