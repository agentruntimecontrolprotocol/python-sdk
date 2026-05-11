"""SQLite replay sink. Reuses the SDK's `arcp.store.eventlog` schema."""

from __future__ import annotations

from arcp import Envelope


class SQLiteSink:
    def __init__(self, *, path: str) -> None:
        self._path = path

    async def __aenter__(self) -> SQLiteSink:
        # Real version: aiosqlite.connect + executescript(schema.sql)
        # using arcp.store.eventlog's shipped schema.
        return self

    async def __aexit__(self, *_exc: object) -> None: ...

    async def handle(self, env: Envelope) -> None:
        # Drops kind: thought to keep the replay store small.
        if env.type == "stream.chunk" and env.payload.get("kind") == "thought":
            return
        # Real version: INSERT OR IGNORE on (id, ts, type, json).
        ...
