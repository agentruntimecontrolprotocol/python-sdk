"""In-memory `(principal, idempotency_key) -> JobAccepted` map with TTL sweep."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IdempotencyEntry:
    """Stored result for a previously-seen idempotency key.

    `terminal_envelope` is `None` while the original job is still running
    and populated with the wire dict of the terminal `job.result` / `job.error`
    envelope when the job reaches a final state. Duplicate submits replay
    both the accepted envelope and (if present) the terminal envelope so
    the caller's handle resolves promptly instead of hanging.
    """

    job_id: str
    accepted_envelope: dict[str, Any]
    submit_fingerprint: str
    expires_at: float
    terminal_envelope: dict[str, Any] | None = None


@dataclass
class IdempotencyStore:
    """Per-principal idempotency map. TTL sweep is amortized into reads/writes."""

    ttl_sec: float = 24 * 60 * 60
    _by_key: dict[tuple[str, str], IdempotencyEntry] = field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]
    _by_job_id: dict[str, tuple[str, str]] = field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]
    _locks: dict[tuple[str, str], asyncio.Lock] = field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]

    @staticmethod
    def fingerprint(submit_payload: dict[str, Any]) -> str:
        """Hash-stable canonical serialization of the submit payload."""
        return json.dumps(submit_payload, sort_keys=True, separators=(",", ":"))

    def lock_for(self, principal: str, key: str) -> asyncio.Lock:
        """Return the per-(principal, key) lock that serializes check-and-store.

        Holding this lock across the (possibly awaiting) job build closes the
        get→put race so two concurrent same-key submits cannot both miss the
        store and mint duplicate jobs / double-issue credentials (§7.2).
        """
        loc = (principal, key)
        lock = self._locks.get(loc)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[loc] = lock
        return lock

    def _sweep(self) -> None:
        now = time.time()
        expired = [k for k, v in self._by_key.items() if v.expires_at <= now]
        for k in expired:
            entry = self._by_key.pop(k)
            self._by_job_id.pop(entry.job_id, None)
            lock = self._locks.get(k)
            # Drop the lock only when nobody is holding/awaiting it, so a slow
            # in-flight submit past TTL is not stranded.
            if lock is not None and not lock.locked():
                self._locks.pop(k, None)

    def get(self, principal: str, key: str) -> IdempotencyEntry | None:
        self._sweep()
        return self._by_key.get((principal, key))

    def put(
        self,
        principal: str,
        key: str,
        *,
        job_id: str,
        accepted_envelope: dict[str, Any],
        submit_fingerprint: str,
    ) -> IdempotencyEntry:
        entry = IdempotencyEntry(
            job_id=job_id,
            accepted_envelope=accepted_envelope,
            submit_fingerprint=submit_fingerprint,
            expires_at=time.time() + self.ttl_sec,
        )
        self._by_key[(principal, key)] = entry
        self._by_job_id[job_id] = (principal, key)
        return entry

    def set_terminal(self, job_id: str, terminal_envelope: dict[str, Any]) -> None:
        """Attach a terminal envelope to the idempotency entry for `job_id`, if any."""
        loc = self._by_job_id.get(job_id)
        if loc is None:
            return
        existing = self._by_key.get(loc)
        if existing is None:
            return
        self._by_key[loc] = dataclasses.replace(existing, terminal_envelope=terminal_envelope)


__all__ = ("IdempotencyEntry", "IdempotencyStore")
