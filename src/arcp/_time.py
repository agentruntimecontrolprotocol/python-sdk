"""Shared UTC timestamp helper used across the SDK."""

from __future__ import annotations

import datetime as dt


def now_iso_z() -> str:
    """Return the current UTC time as an ISO 8601 string with a `Z` suffix."""
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


__all__ = ("now_iso_z",)
