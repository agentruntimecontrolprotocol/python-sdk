"""Artifact storage (RFC §16). v0.1: inline base64 only, SQLite-backed."""

from __future__ import annotations

import base64
import binascii
import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from arcp.errors import ARCPError, ErrorCode
from arcp.store.eventlog import EventLog


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class ArtifactRecord:
    artifact_id: str
    session_id: str
    media_type: str
    size: int
    sha256: str
    expires_at: str | None


class ArtifactStore:
    """Per-runtime artifact store backed by the existing event log SQLite db."""

    def __init__(
        self,
        event_log: EventLog,
        *,
        default_retention_seconds: int = 3600,
        max_retention_seconds: int = 86400,
    ) -> None:
        self._event_log = event_log
        self._default = default_retention_seconds
        self._max = max_retention_seconds

    async def put(
        self,
        *,
        session_id: str,
        media_type: str,
        data_b64: str,
        sha256: str | None = None,
        expires_at: str | None = None,
    ) -> ArtifactRecord:
        try:
            blob = base64.b64decode(data_b64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ARCPError(
                ErrorCode.INVALID_ARGUMENT, f"data is not valid base64: {exc}"
            ) from exc
        digest = hashlib.sha256(blob).hexdigest()
        if sha256 is not None and sha256 != digest:
            raise ARCPError(ErrorCode.INVALID_ARGUMENT, "sha256 does not match payload")
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        if expires_at is None:
            expires_at = (
                datetime.now(tz=UTC) + timedelta(seconds=self._default)
            ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        conn = self._event_log.connection
        await conn.execute(
            """
            INSERT INTO artifacts
                (artifact_id, session_id, media_type, size, sha256, expires_at, blob)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (artifact_id, session_id, media_type, len(blob), digest, expires_at, blob),
        )
        await conn.commit()
        return ArtifactRecord(
            artifact_id=artifact_id,
            session_id=session_id,
            media_type=media_type,
            size=len(blob),
            sha256=digest,
            expires_at=expires_at,
        )

    async def fetch(self, *, session_id: str, artifact_id: str) -> dict[str, Any]:
        conn = self._event_log.connection
        async with conn.execute(
            """
            SELECT media_type, size, sha256, expires_at, released, blob
            FROM artifacts
            WHERE artifact_id = ? AND session_id = ?
            """,
            (artifact_id, session_id),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise ARCPError(ErrorCode.NOT_FOUND, f"artifact {artifact_id!r} not found")
        media_type, size, sha256, expires_at, released, blob = row
        if released:
            raise ARCPError(ErrorCode.NOT_FOUND, f"artifact {artifact_id!r} was released")
        if expires_at is not None and expires_at < _now_iso():
            raise ARCPError(ErrorCode.NOT_FOUND, f"artifact {artifact_id!r} expired")
        return {
            "artifact_id": artifact_id,
            "media_type": media_type,
            "size": size,
            "sha256": sha256,
            "expires_at": expires_at,
            "data": base64.b64encode(blob).decode("ascii"),
        }

    async def release(self, *, session_id: str, artifact_id: str) -> None:
        conn = self._event_log.connection
        cursor = await conn.execute(
            "UPDATE artifacts SET released = 1 WHERE artifact_id = ? AND session_id = ?",
            (artifact_id, session_id),
        )
        await conn.commit()
        affected = cursor.rowcount or 0
        await cursor.close()
        if affected == 0:
            raise ARCPError(ErrorCode.NOT_FOUND, f"artifact {artifact_id!r} not found")

    async def sweep(self) -> int:
        """Delete expired artifacts. Returns the count removed."""

        conn = self._event_log.connection
        cursor = await conn.execute(
            "DELETE FROM artifacts WHERE expires_at IS NOT NULL AND expires_at < ?",
            (_now_iso(),),
        )
        deleted = cursor.rowcount or 0
        await conn.commit()
        await cursor.close()
        return deleted


__all__ = ["ArtifactRecord", "ArtifactStore"]
