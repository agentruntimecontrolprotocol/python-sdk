"""SQLite-backed append-only event log (RFC §6.4, §13.3, §19).

The event log persists every envelope the runtime observes or emits within a
session. It is the source of truth for:

* Transport-id deduplication (§6.4).
* Subscription backfill (§13.3).
* Resume after disconnect (§19).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from importlib import resources
from pathlib import Path
from typing import Any

import aiosqlite

from arcp.envelope import Envelope


class EventLog:
    """Append-only SQLite event log.

    The log is opened against a single database connection per :class:`EventLog`
    instance. ``:memory:`` is supported for tests; pass a file path for durable
    runtimes. The schema is applied on :meth:`open` if absent.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        self._db: aiosqlite.Connection | None = None

    @property
    def path(self) -> str:
        """Path."""
        return self._path

    async def open(self) -> None:
        """Open the SQLite connection and ensure the schema is present."""
        if self._db is not None:
            return
        self._db = await aiosqlite.connect(self._path)
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.execute("PRAGMA foreign_keys=ON;")
        schema = resources.files("arcp.store").joinpath("schema.sql").read_text(encoding="utf-8")
        await self._db.executescript(schema)
        await self._db.commit()

    async def close(self) -> None:
        """Close."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> EventLog:
        await self.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @property
    def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("EventLog is not open; call open() or use 'async with'")
        return self._db

    @property
    def connection(self) -> aiosqlite.Connection:
        """Expose the underlying connection for sibling stores (e.g. artifacts)."""
        return self._conn

    async def append(self, envelope: Envelope) -> bool:
        """Append ``envelope``. Idempotent on ``(session_id, id)``.

        Returns ``True`` if the row was inserted, ``False`` if it already
        existed (i.e. a transport retransmit was deduplicated per §6.4).
        """
        wire = envelope.to_wire()
        body = json.dumps(wire, separators=(",", ":"), sort_keys=True)
        cursor = await self._conn.execute(
            """
            INSERT OR IGNORE INTO events
                (session_id, id, type, job_id, stream_id, subscription_id,
                 trace_id, correlation_id, causation_id, timestamp, priority, envelope)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                envelope.session_id,
                envelope.id,
                envelope.type,
                envelope.job_id,
                envelope.stream_id,
                envelope.subscription_id,
                envelope.trace_id,
                envelope.correlation_id,
                envelope.causation_id,
                envelope.timestamp,
                envelope.priority,
                body,
            ),
        )
        await self._conn.commit()
        inserted = cursor.rowcount == 1
        await cursor.close()
        return inserted

    async def replay(
        self,
        *,
        session_id: str | None = None,
        after_message_id: str | None = None,
    ) -> AsyncIterator[Envelope]:
        """Yield envelopes in canonical replay order.

        When ``session_id`` is provided, only that session's events are returned.
        When ``after_message_id`` is provided, only events with a ``rowid``
        strictly greater than that of the matching row are returned, matching
        the §19 ``after_message_id`` semantics.
        """
        anchor_rowid = 0
        if after_message_id is not None:
            row = await self._fetchone(
                "SELECT rowid FROM events WHERE id = ? AND (session_id = ? OR ? IS NULL)",
                (after_message_id, session_id, session_id),
            )
            if row is None:
                # Anchor not found; signal data loss to the caller via empty replay.
                # The runtime resume path raises ``DATA_LOSS`` based on its own check.
                return
            anchor_rowid = int(row[0])

        if session_id is None:
            sql = "SELECT envelope FROM events WHERE rowid > ? ORDER BY rowid ASC"
            params: tuple[Any, ...] = (anchor_rowid,)
        else:
            sql = (
                "SELECT envelope FROM events WHERE rowid > ? AND session_id = ? ORDER BY rowid ASC"
            )
            params = (anchor_rowid, session_id)

        async with self._conn.execute(sql, params) as cursor:
            async for row in cursor:
                yield Envelope.from_wire(json.loads(row[0]))

    async def has_message(self, *, session_id: str | None, message_id: str) -> bool:
        """Return ``True`` iff ``message_id`` is present for ``session_id``."""
        row = await self._fetchone(
            "SELECT 1 FROM events WHERE id = ? AND (session_id = ? OR ? IS NULL)",
            (message_id, session_id, session_id),
        )
        return row is not None

    async def remember_idempotent(
        self,
        *,
        principal: str,
        idempotency_key: str,
        result: dict[str, Any],
        created_at: str,
    ) -> bool:
        """Persist a logical-intent result. Returns ``False`` if already stored."""
        cursor = await self._conn.execute(
            """
            INSERT OR IGNORE INTO idempotency_results
                (principal, idempotency_key, result_envelope, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                principal,
                idempotency_key,
                json.dumps(result, separators=(",", ":"), sort_keys=True),
                created_at,
            ),
        )
        await self._conn.commit()
        inserted = cursor.rowcount == 1
        await cursor.close()
        return inserted

    async def lookup_idempotent(
        self, *, principal: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        """Return a stored logical-intent result, or ``None`` if absent."""
        row = await self._fetchone(
            "SELECT result_envelope FROM idempotency_results "
            "WHERE principal = ? AND idempotency_key = ?",
            (principal, idempotency_key),
        )
        if row is None:
            return None
        loaded: dict[str, Any] = json.loads(row[0])
        return loaded

    async def gc_before(self, retention_anchor: str) -> int:
        """Delete events strictly older than ``retention_anchor`` (RFC 3339).

        Returns the number of rows removed. Used for the configured retention
        horizon described in §19.
        """
        cursor = await self._conn.execute(
            "DELETE FROM events WHERE timestamp < ?", (retention_anchor,)
        )
        deleted = cursor.rowcount or 0
        await self._conn.commit()
        await cursor.close()
        return deleted

    async def append_all(self, envelopes: Iterable[Envelope]) -> int:
        """Bulk-append. Returns the count actually inserted (post-dedup)."""
        count = 0
        for env in envelopes:
            if await self.append(env):
                count += 1
        return count

    async def _fetchone(self, sql: str, params: tuple[Any, ...]) -> tuple[Any, ...] | None:
        async with self._conn.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return None if row is None else tuple(row)


__all__ = ["EventLog"]
