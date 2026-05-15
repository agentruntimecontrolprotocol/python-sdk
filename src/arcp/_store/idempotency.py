"""In-memory `(principal, idempotency_key) -> JobAccepted` map with TTL sweep."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IdempotencyEntry:
    """Stored result for a previously-seen idempotency key."""

    job_id: str
    accepted_envelope: dict[str, Any]
    submit_fingerprint: str
    expires_at: float


@dataclass
class IdempotencyStore:
    """Per-principal idempotency map. TTL sweep is amortized into reads/writes."""

    ttl_sec: float = 24 * 60 * 60
    _by_key: dict[tuple[str, str], IdempotencyEntry] = field(default_factory=dict)

    @staticmethod
    def fingerprint(submit_payload: dict[str, Any]) -> str:
        """Hash-stable canonical serialization of the submit payload."""
        return json.dumps(submit_payload, sort_keys=True, separators=(",", ":"))

    def _sweep(self) -> None:
        now = time.time()
        expired = [k for k, v in self._by_key.items() if v.expires_at <= now]
        for k in expired:
            del self._by_key[k]

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
        return entry


__all__ = ("IdempotencyEntry", "IdempotencyStore")
