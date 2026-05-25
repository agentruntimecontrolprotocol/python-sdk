"""Unit tests for client-side inbound dispatch handlers (§dispatch)."""

from __future__ import annotations

import datetime as dt
from collections import deque
from unittest.mock import AsyncMock, MagicMock

from arcp._client.dispatch import (
    _on_job_event,
    _on_job_terminal,
    _on_session_bye,
    _on_session_error,
    _on_session_ping,
    build_dispatch_table,
)
from arcp._client.handles import JobHandle
from arcp._envelope import Envelope
from arcp._errors import InternalError
from arcp._messages.execution import JobAcceptedPayload, JobErrorPayload, JobResultPayload
from arcp._messages.session import SessionPingPayload
from arcp._ulid import new_envelope_id, new_ulid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(handles: dict | None = None) -> MagicMock:
    """Return a minimal mock ARCPClient suitable for dispatch testing."""
    client = MagicMock()
    client._session_id = "test-session"
    client._transport = MagicMock()
    client._transport.send = AsyncMock()
    client._handles = handles if handles is not None else {}
    client._fail_all_handles = MagicMock()
    client.close = AsyncMock()
    client._pending = MagicMock()
    client._pending.resolve = MagicMock()
    client._pending_accepts = deque()
    return client


def _make_handle(job_id: str) -> JobHandle:
    """Construct a minimal JobHandle for a given job_id."""
    accepted = JobAcceptedPayload(
        job_id=job_id,
        agent="test-agent",
        accepted_at=dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        lease={},
    )
    return JobHandle(job_id=job_id, accepted=accepted)


def _ping_envelope(nonce: str | None = None) -> Envelope:
    n = nonce or new_ulid()
    ping = SessionPingPayload(nonce=n, sent_at=dt.datetime.now(dt.UTC).isoformat())
    return Envelope(
        id=new_envelope_id(),
        type="session.ping",
        session_id="test-session",
        payload=ping.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# _on_session_ping
# ---------------------------------------------------------------------------


async def test_on_session_ping_sends_pong() -> None:
    """_on_session_ping must send a session.pong envelope with the correct nonce."""
    client = _make_client()
    nonce = new_ulid()
    env = _ping_envelope(nonce)

    await _on_session_ping(client, env)

    client._transport.send.assert_awaited_once()
    # The wire value contains the nonce somewhere (dict or bytes)
    wire = client._transport.send.call_args[0][0]
    assert nonce in str(wire)


async def test_on_session_ping_wire_contains_pong_type() -> None:
    """Wire payload from _on_session_ping encodes type=session.pong."""
    client = _make_client()
    env = _ping_envelope()

    await _on_session_ping(client, env)

    wire = client._transport.send.call_args[0][0]
    # to_wire() may return a dict or bytes depending on transport impl
    if isinstance(wire, bytes):
        assert b"session.pong" in wire
    else:
        assert wire.get("type") == "session.pong"


# ---------------------------------------------------------------------------
# _on_session_error
# ---------------------------------------------------------------------------


async def test_on_session_error_fails_all_handles() -> None:
    """_on_session_error calls _fail_all_handles with an ARCPError instance."""
    client = _make_client()
    env = Envelope(
        id=new_envelope_id(),
        type="session.error",
        session_id="test-session",
        payload={"code": "INTERNAL_ERROR", "message": "boom", "retryable": True},
    )
    await _on_session_error(client, env)

    client._fail_all_handles.assert_called_once()
    exc = client._fail_all_handles.call_args[0][0]
    assert isinstance(exc, InternalError)
    assert exc.message == "boom"


async def test_on_session_error_unknown_code_falls_back_to_internal() -> None:
    """Unknown error codes collapse to InternalError."""
    client = _make_client()
    env = Envelope(
        id=new_envelope_id(),
        type="session.error",
        session_id="test-session",
        payload={"code": "TOTALLY_UNKNOWN_CODE", "message": "?", "retryable": False},
    )
    await _on_session_error(client, env)

    exc = client._fail_all_handles.call_args[0][0]
    assert isinstance(exc, InternalError)


# ---------------------------------------------------------------------------
# _on_session_bye
# ---------------------------------------------------------------------------


async def test_on_session_bye_calls_close() -> None:
    """_on_session_bye calls client.close(reason='peer.bye')."""
    client = _make_client()
    env = Envelope(
        id=new_envelope_id(),
        type="session.bye",
        session_id="test-session",
        payload={},
    )
    await _on_session_bye(client, env)

    client.close.assert_awaited_once_with(reason="peer.bye")


# ---------------------------------------------------------------------------
# _on_job_event
# ---------------------------------------------------------------------------


async def test_on_job_event_result_chunk_calls_push_chunk() -> None:
    """result_chunk kind routes to handle._push_chunk."""
    handle = _make_handle("job-1")
    handle._push_chunk = MagicMock()
    client = _make_client(handles={"job-1": handle})

    env = Envelope(
        id=new_envelope_id(),
        type="job.event",
        session_id="test-session",
        job_id="job-1",
        payload={"kind": "result_chunk", "body": {"data": "hello"}, "ts": "2024-01-01T00:00:00Z"},
    )
    await _on_job_event(client, env)

    handle._push_chunk.assert_called_once_with({"data": "hello"})


async def test_on_job_event_non_chunk_calls_push_event() -> None:
    """Non-chunk kind routes to handle._push_event."""
    handle = _make_handle("job-2")
    handle._push_event = MagicMock()
    client = _make_client(handles={"job-2": handle})

    env = Envelope(
        id=new_envelope_id(),
        type="job.event",
        session_id="test-session",
        job_id="job-2",
        payload={
            "kind": "log",
            "body": {"level": "info", "message": "hi"},
            "ts": "2024-01-01T00:00:00Z",
        },
    )
    await _on_job_event(client, env)

    handle._push_event.assert_called_once()
    pushed = handle._push_event.call_args[0][0]
    assert pushed["kind"] == "log"
    assert pushed["body"]["message"] == "hi"


async def test_on_job_event_no_job_id_is_noop() -> None:
    """job_id=None must be silently ignored."""
    handle = _make_handle("job-3")
    handle._push_chunk = MagicMock()
    handle._push_event = MagicMock()
    client = _make_client(handles={"job-3": handle})

    env = Envelope(
        id=new_envelope_id(),
        type="job.event",
        session_id="test-session",
        job_id=None,
        payload={"kind": "result_chunk", "body": {}, "ts": ""},
    )
    await _on_job_event(client, env)

    handle._push_chunk.assert_not_called()
    handle._push_event.assert_not_called()


async def test_on_job_event_unknown_job_id_is_noop() -> None:
    """Unknown job_id must be silently ignored."""
    client = _make_client(handles={})

    env = Envelope(
        id=new_envelope_id(),
        type="job.event",
        session_id="test-session",
        job_id="ghost-job",
        payload={"kind": "result_chunk", "body": {}, "ts": ""},
    )
    # Must not raise
    await _on_job_event(client, env)


# ---------------------------------------------------------------------------
# _on_job_terminal — result path
# ---------------------------------------------------------------------------


async def test_on_job_terminal_result_resolves_handle() -> None:
    """terminal_kind='result' calls _resolve_terminal and removes handle from _handles."""
    handle = _make_handle("job-ok")
    handle._resolve_terminal = MagicMock()
    handles = {"job-ok": handle}
    client = _make_client(handles=handles)

    result_payload = JobResultPayload(
        final_status="success",
        completed_at=dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
    )
    env = Envelope(
        id=new_envelope_id(),
        type="job.result",
        session_id="test-session",
        job_id="job-ok",
        payload=result_payload.model_dump(mode="json"),
    )
    await _on_job_terminal(client, env, terminal_kind="result")

    handle._resolve_terminal.assert_called_once()
    assert "job-ok" not in handles


async def test_on_job_terminal_error_rejects_handle() -> None:
    """terminal_kind='error' calls _reject_terminal and removes handle from _handles."""
    handle = _make_handle("job-err")
    handle._reject_terminal = MagicMock()
    handles = {"job-err": handle}
    client = _make_client(handles=handles)

    error_payload = JobErrorPayload(
        code="INTERNAL_ERROR",
        message="agent crashed",
        retryable=False,
        final_status="error",
        completed_at=dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
    )
    env = Envelope(
        id=new_envelope_id(),
        type="job.error",
        session_id="test-session",
        job_id="job-err",
        payload=error_payload.model_dump(mode="json"),
    )
    await _on_job_terminal(client, env, terminal_kind="error")

    handle._reject_terminal.assert_called_once()
    exc = handle._reject_terminal.call_args[0][0]
    assert isinstance(exc, InternalError)
    assert "job-err" not in handles


async def test_on_job_terminal_no_job_id_is_noop() -> None:
    """terminal_kind with job_id=None is silently ignored."""
    client = _make_client()
    env = Envelope(
        id=new_envelope_id(),
        type="job.result",
        session_id="test-session",
        job_id=None,
        payload={},
    )
    # Must not raise
    await _on_job_terminal(client, env, terminal_kind="result")


async def test_on_job_terminal_unknown_job_id_is_noop() -> None:
    """Pop of unknown job_id from _handles must be silently ignored."""
    client = _make_client(handles={})
    env = Envelope(
        id=new_envelope_id(),
        type="job.result",
        session_id="test-session",
        job_id="ghost",
        payload={},
    )
    await _on_job_terminal(client, env, terminal_kind="result")


# ---------------------------------------------------------------------------
# build_dispatch_table — smoke test
# ---------------------------------------------------------------------------


def test_build_dispatch_table_has_all_verbs() -> None:
    """build_dispatch_table returns a handler for every expected verb."""
    client = _make_client()
    table = build_dispatch_table(client)
    expected_verbs = {
        "session.ping",
        "session.pong",
        "session.error",
        "session.bye",
        "session.jobs",
        "job.subscribed",
        "job.accepted",
        "job.event",
        "job.result",
        "job.error",
    }
    assert expected_verbs == set(table.keys())
