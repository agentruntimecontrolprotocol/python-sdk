"""#74 — a single UTC timestamp helper backs every former `_now_iso` copy."""

from __future__ import annotations

import datetime as dt

from arcp._client import dispatch as client_dispatch
from arcp._client import ops as client_ops
from arcp._runtime import _handlers, _handshake, _job_runner, job, result_stream
from arcp._time import now_iso_z


def test_now_iso_z_is_utc_with_z_suffix() -> None:
    value = now_iso_z()
    assert value.endswith("Z")
    assert "+00:00" not in value
    parsed = dt.datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == dt.timedelta(0)


def test_former_copies_share_the_single_helper() -> None:
    # Every module that previously defined its own `_now_iso`/`_now_iso_z`
    # now binds the shared `arcp._time.now_iso_z` (#74 DRY).
    assert job._now_iso is now_iso_z
    assert _job_runner._now_iso is now_iso_z
    assert _handlers._now_iso is now_iso_z
    assert _handshake._now_iso is now_iso_z
    assert result_stream._now_iso_z is now_iso_z
    assert client_dispatch._now_iso is now_iso_z
    assert client_ops._now_iso is now_iso_z
