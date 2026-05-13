"""Unit tests for arcp.client.client error and edge paths.

Integration tests cover the happy handshake path against a real runtime;
these tests exercise the protocol-fault branches by driving the server
side of an in-memory transport pair directly.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

import pytest

from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode
from arcp.messages.session import (
    AuthBlock,
    Capabilities,
    Identity,
    RuntimeIdentity,
    SessionAcceptedPayload,
)
from arcp.transport.in_memory import InMemoryTransport, create_pair


def _client(transport: InMemoryTransport) -> ARCPClient:
    return ARCPClient(
        transport=transport,
        client_identity=Identity(kind="t", version="1"),
        auth=AuthBlock(scheme="none"),
        capabilities=Capabilities(anonymous=True),
    )


def _accepted_payload(session_id: str = "sess_test") -> dict[str, object]:
    return SessionAcceptedPayload(
        session_id=session_id,
        runtime=RuntimeIdentity(kind="rt", version="1"),
        capabilities=Capabilities(anonymous=True),
    ).model_dump(exclude_none=True)


@asynccontextmanager
async def _running_server(
    handler: Callable[[InMemoryTransport], Coroutine[Any, Any, None]],
    server_t: InMemoryTransport,
) -> AsyncGenerator[asyncio.Task[None]]:
    task: asyncio.Task[None] = asyncio.create_task(handler(server_t))
    try:
        yield task
    finally:
        if not task.done():
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


@pytest.mark.asyncio
async def test_negotiated_capabilities_before_open_raises() -> None:
    client_t, _ = create_pair()
    client = _client(client_t)
    with pytest.raises(RuntimeError, match="has not completed handshake"):
        _ = client.negotiated_capabilities


@pytest.mark.asyncio
async def test_open_twice_raises() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async def server(t: InMemoryTransport) -> None:
        raw = await t.recv()
        await t.send(
            Envelope(
                id="msg_a",
                type="session.accepted",
                correlation_id=raw["id"],
                payload=_accepted_payload(),
            ).to_wire()
        )

    async with _running_server(server, server_t):
        await client.open()
        with pytest.raises(RuntimeError, match="already open"):
            await client.open()
        await client.close()


@pytest.mark.asyncio
async def test_open_drops_pre_accept_out_of_band_envelope() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async def server(t: InMemoryTransport) -> None:
        raw = await t.recv()
        # Out-of-band envelope with no matching correlation_id — must be dropped.
        await t.send(Envelope(id="msg_oob", type="server.note", payload={}).to_wire())
        await t.send(
            Envelope(
                id="msg_a",
                type="session.accepted",
                correlation_id=raw["id"],
                payload=_accepted_payload(),
            ).to_wire()
        )

    async with _running_server(server, server_t):
        accepted = await client.open()
        assert accepted.session_id == "sess_test"
        await client.close()


@pytest.mark.asyncio
async def test_open_session_rejected_raises_arcp_error() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async def server(t: InMemoryTransport) -> None:
        raw = await t.recv()
        await t.send(
            Envelope(
                id="msg_r",
                type="session.rejected",
                correlation_id=raw["id"],
                payload={"code": str(ErrorCode.PERMISSION_DENIED), "message": "no"},
            ).to_wire()
        )

    async with _running_server(server, server_t):
        with pytest.raises(ARCPError) as exc:
            await client.open()
        assert exc.value.code == ErrorCode.PERMISSION_DENIED
        assert "no" in str(exc.value)


@pytest.mark.asyncio
async def test_open_session_rejected_defaults_message_when_absent() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async def server(t: InMemoryTransport) -> None:
        raw = await t.recv()
        # Payload without code or message → default UNAUTHENTICATED + canned text.
        await t.send(
            Envelope(
                id="msg_r",
                type="session.rejected",
                correlation_id=raw["id"],
                payload={},
            ).to_wire()
        )

    async with _running_server(server, server_t):
        with pytest.raises(ARCPError) as exc:
            await client.open()
        assert exc.value.code == ErrorCode.UNAUTHENTICATED
        assert "session rejected" in str(exc.value)


@pytest.mark.asyncio
async def test_open_handles_challenge_then_accept() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async def server(t: InMemoryTransport) -> None:
        opened = await t.recv()
        # Issue a challenge correlated to the open envelope.
        await t.send(
            Envelope(
                id="msg_chal",
                type="session.challenge",
                correlation_id=opened["id"],
                payload={"nonce": "n"},
            ).to_wire()
        )
        # Client should respond with session.authenticate carrying auth block.
        auth_msg = await t.recv()
        assert auth_msg["type"] == "session.authenticate"
        assert auth_msg["payload"]["auth"]["scheme"] == "none"
        # Finally accept correlated to the original open id.
        await t.send(
            Envelope(
                id="msg_acc",
                type="session.accepted",
                correlation_id=opened["id"],
                payload=_accepted_payload(),
            ).to_wire()
        )

    async with _running_server(server, server_t):
        accepted = await client.open()
        assert accepted.session_id == "sess_test"
        await client.close()


@pytest.mark.asyncio
async def test_open_unexpected_envelope_type_raises_internal() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async def server(t: InMemoryTransport) -> None:
        raw = await t.recv()
        await t.send(
            Envelope(
                id="msg_x",
                type="session.weird",
                correlation_id=raw["id"],
                payload={},
            ).to_wire()
        )

    async with _running_server(server, server_t):
        with pytest.raises(ARCPError) as exc:
            await client.open()
        assert exc.value.code == ErrorCode.INTERNAL


@pytest.mark.asyncio
async def test_send_before_open_raises() -> None:
    client_t, _ = create_pair()
    client = _client(client_t)
    env = Envelope(id="msg_x", type="job.invoke", payload={})
    with pytest.raises(RuntimeError, match="not open"):
        await client.send(env)


@pytest.mark.asyncio
async def test_request_before_open_raises() -> None:
    client_t, _ = create_pair()
    client = _client(client_t)
    env = Envelope(id="msg_x", type="job.invoke", payload={})
    with pytest.raises(RuntimeError, match="not open"):
        await client.request(env)


def test_envelope_factory_passes_through_all_fields() -> None:
    client_t, _ = create_pair()
    client = _client(client_t)
    client.session_id = "sess_x"

    env = client.envelope(
        "tool.invoke",
        payload={"k": "v"},
        job_id="job_1",
        stream_id="stm_1",
        subscription_id="sub_1",
        correlation_id="cor_1",
        causation_id="cau_1",
        trace_id="trc_1",
        idempotency_key="idk_1",
        priority="high",
        target="agent.alice",
        extensions={"arcpx.acme.thing.v1": {"x": 1}},
    )
    assert env.type == "tool.invoke"
    assert env.session_id == "sess_x"
    assert env.payload == {"k": "v"}
    assert env.job_id == "job_1"
    assert env.stream_id == "stm_1"
    assert env.subscription_id == "sub_1"
    assert env.correlation_id == "cor_1"
    assert env.causation_id == "cau_1"
    assert env.trace_id == "trc_1"
    assert env.idempotency_key == "idk_1"
    assert env.priority == "high"
    assert env.target == "agent.alice"
    assert env.extensions == {"arcpx.acme.thing.v1": {"x": 1}}


def test_envelope_factory_defaults_payload_to_empty_dict() -> None:
    client_t, _ = create_pair()
    client = _client(client_t)
    client.session_id = "sess_x"
    env = client.envelope("ping")
    assert env.payload == {}
    assert env.session_id == "sess_x"


async def _accept_and_close(t: InMemoryTransport) -> None:
    raw = await t.recv()
    await t.send(
        Envelope(
            id="msg_a",
            type="session.accepted",
            correlation_id=raw["id"],
            payload=_accepted_payload(),
        ).to_wire()
    )


@pytest.mark.asyncio
async def test_events_returns_when_close_signals_eof() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async with _running_server(_accept_and_close, server_t):
        await client.open()
    await client.close()

    seen = [env async for env in client.events()]
    # close() pushes a None sentinel which terminates the iterator immediately.
    assert seen == []


@pytest.mark.asyncio
async def test_close_is_idempotent() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async with _running_server(_accept_and_close, server_t):
        await client.open()
        await client.close()
        # Second close must early-return without raising.
        await client.close()


@pytest.mark.asyncio
async def test_reader_loop_routes_uncorrelated_envelopes_to_events() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async def server(t: InMemoryTransport) -> None:
        raw = await t.recv()
        await t.send(
            Envelope(
                id="msg_a",
                type="session.accepted",
                correlation_id=raw["id"],
                payload=_accepted_payload(),
            ).to_wire()
        )
        # Push an event with no correlation_id — reader loop lands it on events queue.
        await t.send(Envelope(id="msg_evt", type="job.completed", payload={"ok": True}).to_wire())

    async with _running_server(server, server_t):
        await client.open()
        iterator = client.events().__aiter__()
        env = await asyncio.wait_for(iterator.__anext__(), timeout=1.0)
        assert env.type == "job.completed"
        await client.close()


@pytest.mark.asyncio
async def test_reader_loop_exits_on_transport_closed() -> None:
    client_t, server_t = create_pair()
    client = _client(client_t)

    async def server(t: InMemoryTransport) -> None:
        raw = await t.recv()
        await t.send(
            Envelope(
                id="msg_a",
                type="session.accepted",
                correlation_id=raw["id"],
                payload=_accepted_payload(),
            ).to_wire()
        )
        # Close server side; client's reader_loop hits TransportClosed and exits.
        await t.close()

    async with _running_server(server, server_t):
        await client.open()
        seen = [env async for env in client.events()]
        # No events were emitted before close.
        assert seen == []
        await client.close()
