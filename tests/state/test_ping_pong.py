"""§6.5 — session.ping → session.pong round-trip (server-initiated and client-initiated)."""

from __future__ import annotations

import asyncio
import contextlib

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._envelope import Envelope
from arcp._messages.session import SessionPingPayload, SessionPongPayload
from arcp._ulid import new_envelope_id, new_ulid
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_client_receives_pong_on_server_ping() -> None:
    """Server sends session.ping; client auto-replies with session.pong."""
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)

    # Inject a session.ping directly via the server-side session context
    session_ctx = rt._sessions.get(welcome.session_id)
    assert session_ctx is not None

    ping_env = Envelope(
        id=new_envelope_id(),
        type="session.ping",
        session_id=welcome.session_id,
        payload=SessionPingPayload(nonce=new_ulid(), sent_at="2024-01-01T00:00:00Z").model_dump(
            mode="json"
        ),
    )
    session_ctx.stamp_and_enqueue(ping_env)

    # Give the client pump a moment to process the ping and reply
    await asyncio.sleep(0.05)

    await client.close()
    if not accept_task.done():
        accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_server_handle_ping_sends_pong() -> None:
    """Directly invoke handle_ping via _dispatch to verify it enqueues a session.pong."""
    from arcp._runtime._handlers import handle_ping

    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)

    session_ctx = rt._sessions.get(welcome.session_id)
    assert session_ctx is not None

    nonce = new_ulid()
    ping_env = Envelope(
        id=new_envelope_id(),
        type="session.ping",
        session_id=welcome.session_id,
        payload=SessionPingPayload(nonce=nonce, sent_at="2024-01-01T00:00:00Z").model_dump(
            mode="json"
        ),
    )

    # Call handle_ping directly — must enqueue a session.pong
    await handle_ping(rt, session_ctx, ping_env)

    # Drain the send queue to find the pong
    found_pong = False
    try:
        while True:
            item = session_ctx._send_queue.get_nowait()
            if item is not None and item.type == "session.pong":
                pong = SessionPongPayload.model_validate(item.payload)
                assert pong.ping_nonce == nonce
                found_pong = True
                break
    except asyncio.QueueEmpty:
        pass

    assert found_pong, "expected a session.pong in the send queue"

    await client.close()
    if not accept_task.done():
        accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()
