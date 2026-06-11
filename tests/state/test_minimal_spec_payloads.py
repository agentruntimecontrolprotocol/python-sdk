"""#88 — spec-conformant peers may omit accepted_at/completed_at."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import ClientInfo, pair_memory_transports
from arcp._envelope import Envelope
from arcp._messages.execution import JobErrorPayload, JobResultPayload
from arcp._messages.session import SessionWelcomePayload
from arcp._ulid import new_envelope_id, new_session_id
from arcp.client import ARCPClient


def test_welcome_parses_without_accepted_at() -> None:
    payload = {
        "runtime": {"name": "rt", "version": "1.1.0"},
        "session_id": "sess_x",
        "resume_token": "rtk_x",
        "resume_window_sec": 600,
        "capabilities": {"encodings": ["json"], "features": []},
    }
    w = SessionWelcomePayload.model_validate(payload)
    assert w.accepted_at is None


def test_job_result_and_error_parse_without_completed_at() -> None:
    r = JobResultPayload.model_validate(
        {"final_status": "success", "result_id": "res_1", "result_size": 3, "summary": "ok"}
    )
    assert r.completed_at is None
    e = JobErrorPayload.model_validate(
        {"code": "INTERNAL_ERROR", "message": "boom", "retryable": True}
    )
    assert e.completed_at is None


async def test_connect_succeeds_when_welcome_omits_accepted_at() -> None:
    """A minimal §6.2 welcome (no accepted_at) lets connect() complete."""
    server_t, client_t = pair_memory_transports()

    async def minimal_server() -> None:
        hello = await server_t.recv()
        assert hello["type"] == "session.hello"
        welcome = Envelope(
            id=new_envelope_id(),
            type="session.welcome",
            session_id=new_session_id(),
            payload={
                "runtime": {"name": "rt", "version": "1.1.0"},
                "session_id": new_session_id(),
                "resume_token": "rtk_minimal",
                "resume_window_sec": 600,
                "capabilities": {"encodings": ["json"], "features": []},
                # NOTE: no `accepted_at`.
            },
        )
        await server_t.send(welcome.to_wire())

    server_task = asyncio.create_task(minimal_server())
    client = ARCPClient(client=ClientInfo(name="c", version="1"), token="tok")
    try:
        welcome = await client.connect(client_t)
        assert welcome.accepted_at is None
        assert welcome.resume_token == "rtk_minimal"
    finally:
        with contextlib.suppress(Exception):
            await client.close()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await server_task


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
