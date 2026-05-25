"""ARCP wire envelope (spec §5.1): 8 fields, `arcp` constant, mutable pydantic model.

The model is intentionally mutable (frozen=False) so the runtime can stamp
routing metadata (event_seq, session_id) in place on the hot send path and
copy with `model_copy(update=...)` for replay/forwarding. The set of fields
is fixed by spec §5.1; `extra="allow"` preserves forward-compatible vendor
extensions verbatim.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._version import PROTOCOL_VERSION

_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_UUID7_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_PREFIXED_ID_RE = re.compile(r"^[a-z]+_[0-9A-HJKMNP-TV-Z]{26}$")


def _is_valid_id(value: str) -> bool:
    return bool(_ULID_RE.match(value) or _UUID7_RE.match(value) or _PREFIXED_ID_RE.match(value))


def _is_valid_trace_id(value: str) -> bool:
    return bool(_TRACE_ID_RE.match(value)) and value != "0" * 32


class Envelope(BaseModel):
    """Outer envelope for every wire frame. 8 fields per spec §5.1.

    The model stays mutable so runtime code can stamp routing metadata
    and copy envelopes with `model_copy(update=...)` when needed.
    """

    model_config = ConfigDict(extra="allow", frozen=False, populate_by_name=True)

    arcp: str = Field(default=PROTOCOL_VERSION)
    id: str
    type: str
    session_id: str | None = None
    trace_id: str | None = None
    job_id: str | None = None
    event_seq: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("arcp")
    @classmethod
    def _check_arcp(cls, v: str) -> str:
        if v != PROTOCOL_VERSION:
            raise ValueError(f"arcp must be {PROTOCOL_VERSION!r}, got {v!r}")
        return v

    @field_validator("id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not _is_valid_id(v):
            raise ValueError(f"id must be a ULID or UUIDv7, got {v!r}")
        return v

    @field_validator("trace_id")
    @classmethod
    def _check_trace_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _is_valid_trace_id(v):
            raise ValueError(
                "trace_id must be 32 lowercase hex chars and non-zero (W3C TraceContext)"
            )
        return v

    @field_validator("event_seq")
    @classmethod
    def _check_event_seq(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if v < 1:
            raise ValueError("event_seq must be a positive integer")
        return v

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> Envelope:
        """Parse a JSON-decoded dict; preserves unknown top-level fields verbatim."""
        return cls.model_validate(data)

    def to_wire(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict; omits None-valued optionals."""
        return self.model_dump(mode="json", exclude_none=True)


__all__ = ("Envelope",)
