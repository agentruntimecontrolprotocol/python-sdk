"""Tests for unknown-message handling (RFC §21.3)."""

from __future__ import annotations

import asyncio

import pytest

from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.runtime.server import ARCPRuntime


@pytest.mark.asyncio
async def test_unknown_core_type_yields_nack(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()
    bogus = Envelope(
        id="msg_bogus_core",
        type="tool.bogus_subtype",
        session_id=accepted.session_id,
        payload={},
    )
    nack = await client.request(bogus, timeout=2.0)
    assert nack.type == "nack"
    assert nack.payload["code"] == "UNIMPLEMENTED"


@pytest.mark.asyncio
async def test_unknown_namespaced_required_nacks(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()
    msg = Envelope(
        id="msg_ns_req",
        type="arcpx.acme.thing.v1",
        session_id=accepted.session_id,
        payload={},
    )
    nack = await client.request(msg, timeout=2.0)
    assert nack.type == "nack"
    assert nack.payload["code"] == "UNIMPLEMENTED"


@pytest.mark.asyncio
async def test_unknown_namespaced_optional_drops(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, _, _ = connected
    accepted = await client.open()
    msg = Envelope(
        id="msg_ns_opt",
        type="arcpx.acme.thing.v1",
        session_id=accepted.session_id,
        extensions={"optional": True},
        payload={},
    )
    # Send and a follow-up ping; if drop happened, ping still works.
    await client.send(msg)
    ping = Envelope(
        id="msg_after_drop",
        type="ping",
        session_id=accepted.session_id,
        payload={"nonce": "x"},
    )
    pong = await client.request(ping, timeout=2.0)
    assert pong.type == "pong"
