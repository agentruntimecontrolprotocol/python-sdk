"""Stream lifecycle and backpressure (RFC §11)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import structlog

from arcp.errors import ARCPError, ErrorCode
from arcp.messages.streaming import StreamKind

logger = structlog.get_logger("arcp.stream")


@dataclass
class StreamState:
    """Per-stream bookkeeping."""

    stream_id: str
    session_id: str
    job_id: str | None
    kind: StreamKind
    content_type: str | None = None
    sequence: int = 0
    closed: bool = False
    desired_rate_per_second: int | None = None
    last_emit_ts: float = 0.0


class StreamManager:
    """Tracks open streams per session.

    The manager is intentionally minimal: it allocates monotonic per-stream
    sequence numbers and applies any active backpressure rate-limit before
    yielding the next chunk envelope.
    """

    def __init__(self) -> None:
        self._streams: dict[str, StreamState] = {}

    def open(
        self,
        *,
        session_id: str,
        job_id: str | None,
        kind: StreamKind,
        content_type: str | None = None,
        stream_id: str | None = None,
    ) -> StreamState:
        """Open."""
        sid = stream_id or f"str_{uuid.uuid4().hex[:12]}"
        if sid in self._streams:
            raise ARCPError(ErrorCode.ALREADY_EXISTS, f"stream {sid!r} already open")
        state = StreamState(
            stream_id=sid,
            session_id=session_id,
            job_id=job_id,
            kind=kind,
            content_type=content_type,
        )
        self._streams[sid] = state
        return state

    def get(self, stream_id: str) -> StreamState:
        """Get."""
        state = self._streams.get(stream_id)
        if state is None:
            raise ARCPError(ErrorCode.NOT_FOUND, f"stream {stream_id!r} not open")
        return state

    def close(self, stream_id: str) -> StreamState:
        """Close."""
        state = self.get(stream_id)
        state.closed = True
        return state

    def apply_backpressure(self, stream_id: str, desired_rate: int | None) -> None:
        """Apply backpressure."""
        state = self.get(stream_id)
        state.desired_rate_per_second = desired_rate

    async def throttle(self, stream_id: str) -> None:
        """Sleep as needed to honor a backpressure-set ``desired_rate_per_second``."""
        state = self.get(stream_id)
        if state.desired_rate_per_second is None or state.desired_rate_per_second <= 0:
            return
        loop = asyncio.get_running_loop()
        now = loop.time()
        min_gap = 1.0 / state.desired_rate_per_second
        delta = now - state.last_emit_ts
        if delta < min_gap:
            await asyncio.sleep(min_gap - delta)
        state.last_emit_ts = loop.time()

    def next_sequence(self, stream_id: str) -> int:
        """Next sequence."""
        state = self.get(stream_id)
        seq = state.sequence
        state.sequence += 1
        return seq


__all__ = ["StreamManager", "StreamState"]
