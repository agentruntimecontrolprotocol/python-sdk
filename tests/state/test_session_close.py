"""#68 — graceful close uses session.close/session.closed (§6.7)."""

from __future__ import annotations

import asyncio
import contextlib

from arcp import RuntimeInfo, pair_memory_transports
from arcp._envelope import Envelope
from arcp._messages.session import (
    AuthBearer,
    Capabilities,
    ClientInfo,
    SessionClosePayload,
    SessionHelloPayload,
)
from arcp._ulid import new_envelope_id
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_session_close_is_acknowledged_with_session_closed() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    try:
        hello = Envelope(
            id=new_envelope_id(),
            type="session.hello",
            payload=SessionHelloPayload(
                client=ClientInfo(name="c", version="1"),
                auth=AuthBearer(token="tok"),
                capabilities=Capabilities(),
            ).model_dump(mode="json", exclude_none=True),
        )
        await client_t.send(hello.to_wire())
        welcome = Envelope.from_wire(await client_t.recv())
        assert welcome.type == "session.welcome"

        close = Envelope(
            id=new_envelope_id(),
            type="session.close",
            session_id=welcome.session_id,
            payload=SessionClosePayload(reason="client.done").model_dump(
                mode="json", exclude_none=True
            ),
        )
        await client_t.send(close.to_wire())

        ack = Envelope.from_wire(await asyncio.wait_for(client_t.recv(), timeout=2.0))
        assert ack.type == "session.closed"
        assert ack.session_id == welcome.session_id
    finally:
        with contextlib.suppress(Exception):
            await client_t.close()
        accept_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await accept_task
        await rt.close()
