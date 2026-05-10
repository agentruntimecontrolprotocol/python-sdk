"""Integration tests for §8 handshake."""

from __future__ import annotations

import asyncio

import pytest

from arcp.auth.bearer import StaticTokenValidator
from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode
from arcp.messages.session import AuthBlock, Capabilities, Identity, RuntimeIdentity
from arcp.runtime.server import ARCPRuntime, RuntimeConfig
from arcp.transport.in_memory import create_pair
from tests.integration.conftest import default_advertised


@pytest.mark.asyncio
async def test_bearer_handshake_happy_path(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()
    assert accepted.session_id.startswith("sess_")
    assert accepted.runtime.kind == "reference"
    assert client.negotiated_capabilities.streaming is True
    assert client.negotiated_capabilities.human_input is True


@pytest.mark.asyncio
async def test_bearer_bad_token_rejected() -> None:
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="rt", version="1"),
            advertised_capabilities=default_advertised(),
            bearer_validator=StaticTokenValidator({"good": "alice"}),
        )
    )
    await rt.start()
    try:
        client_t, server_t = create_pair()
        task = asyncio.create_task(rt.serve_session(server_t))
        client = ARCPClient(
            transport=client_t,
            client_identity=Identity(kind="t", version="1"),
            auth=AuthBlock(scheme="bearer", token="bad"),
            capabilities=Capabilities(),
        )
        with pytest.raises(ARCPError) as exc_info:
            await client.open()
        assert exc_info.value.code == ErrorCode.UNAUTHENTICATED
        await client.close()
        task.cancel()
        try:
            await task
        except BaseException:
            pass
    finally:
        await rt.close()


@pytest.mark.asyncio
async def test_anonymous_rejected_without_negotiation() -> None:
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="rt", version="1"),
            advertised_capabilities=default_advertised(),  # anonymous=False
        )
    )
    await rt.start()
    try:
        client_t, server_t = create_pair()
        task = asyncio.create_task(rt.serve_session(server_t))
        client = ARCPClient(
            transport=client_t,
            client_identity=Identity(kind="t", version="1"),
            auth=AuthBlock(scheme="none"),
            capabilities=Capabilities(),
        )
        with pytest.raises(ARCPError) as exc:
            await client.open()
        assert exc.value.code == ErrorCode.UNAUTHENTICATED
        await client.close()
        task.cancel()
        try:
            await task
        except BaseException:
            pass
    finally:
        await rt.close()


@pytest.mark.asyncio
async def test_anonymous_accepted_when_negotiated() -> None:
    advertised = default_advertised().model_copy(update={"anonymous": True})
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="rt", version="1"),
            advertised_capabilities=advertised,
        )
    )
    await rt.start()
    try:
        client_t, server_t = create_pair()
        task = asyncio.create_task(rt.serve_session(server_t))
        client = ARCPClient(
            transport=client_t,
            client_identity=Identity(kind="t", version="1", principal="anon"),
            auth=AuthBlock(scheme="none"),
            capabilities=Capabilities(anonymous=True),
        )
        accepted = await client.open()
        assert accepted.capabilities.anonymous is True
        await client.close()
        task.cancel()
        try:
            await task
        except BaseException:
            pass
    finally:
        await rt.close()


@pytest.mark.asyncio
async def test_required_unsupported_capability_rejected() -> None:
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="rt", version="1"),
            advertised_capabilities=Capabilities(streaming=False),  # no streaming
            bearer_validator=StaticTokenValidator({"good": "alice"}),
        )
    )
    await rt.start()
    try:
        client_t, server_t = create_pair()
        task = asyncio.create_task(rt.serve_session(server_t))
        client = ARCPClient(
            transport=client_t,
            client_identity=Identity(kind="t", version="1"),
            auth=AuthBlock(scheme="bearer", token="good"),
            capabilities=Capabilities(streaming=True),
        )
        with pytest.raises(ARCPError) as exc:
            await client.open()
        assert exc.value.code == ErrorCode.UNIMPLEMENTED
        await client.close()
        task.cancel()
        try:
            await task
        except BaseException:
            pass
    finally:
        await rt.close()


@pytest.mark.asyncio
async def test_pre_acceptance_message_dropped() -> None:
    """A non-handshake first message must be rejected with session.unauthenticated."""

    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="rt", version="1"),
            advertised_capabilities=default_advertised(),
            bearer_validator=StaticTokenValidator({"good": "alice"}),
        )
    )
    await rt.start()
    try:
        client_t, server_t = create_pair()
        task = asyncio.create_task(rt.serve_session(server_t))
        # Send ping before session.open.
        ping = Envelope(id="msg_ping_first", type="ping")
        await client_t.send(ping.to_wire())
        raw = await client_t.recv()
        env = Envelope.from_wire(raw)
        assert env.type == "session.unauthenticated"
        assert env.correlation_id == "msg_ping_first"
        await client_t.close()
        task.cancel()
        try:
            await task
        except BaseException:
            pass
    finally:
        await rt.close()


@pytest.mark.asyncio
async def test_post_handshake_ping_pong(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()
    ping = Envelope(
        id="msg_ping_1",
        type="ping",
        session_id=accepted.session_id,
        payload={"nonce": "abc"},
    )
    pong = await client.request(ping, timeout=2.0)
    assert pong.type == "pong"
    assert pong.payload.get("nonce") == "abc"
