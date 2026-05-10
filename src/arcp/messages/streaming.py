"""Streaming payloads (RFC §11)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StreamKind = Literal["text", "binary", "event", "log", "metric", "thought"]


class StreamOpenPayload(BaseModel):
    """Open a new stream (§11.1)."""

    model_config = ConfigDict(extra="forbid")
    kind: StreamKind
    content_type: str | None = None
    encoding: str | None = None


class StreamChunkPayload(BaseModel):
    """A chunk on an open stream.

    Chunk shapes vary by ``kind``:

    * ``text``/``log``: ``content`` carries the text.
    * ``event``/``metric``: ``content`` is a structured object.
    * ``binary``: ``data`` is base64; ``content_type`` and optional ``sha256``
      may be set on the chunk for per-chunk metadata.
    * ``thought``: see §11.4 — ``role``/``content``/``redacted``.
    """

    model_config = ConfigDict(extra="allow")
    sequence: int = Field(ge=0)
    content: Any | None = None
    data: str | None = None
    role: str | None = None
    redacted: bool | None = None
    content_type: str | None = None
    sha256: str | None = None


class StreamClosePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = None


class StreamErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    retryable: bool | None = None


PAYLOADS: dict[str, type[BaseModel]] = {
    "stream.open": StreamOpenPayload,
    "stream.chunk": StreamChunkPayload,
    "stream.close": StreamClosePayload,
    "stream.error": StreamErrorPayload,
}


__all__ = [
    "PAYLOADS",
    "StreamChunkPayload",
    "StreamClosePayload",
    "StreamErrorPayload",
    "StreamKind",
    "StreamOpenPayload",
]
