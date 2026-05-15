"""§6.2 — handshake happy path and authentication failure."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    UnauthenticatedError,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_hello_welcome_happy_path() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"t": "p1"}),
        heartbeat_interval_sec=None,
    )
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="t",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    assert welcome.session_id.startswith("sess_")
    assert welcome.resume_token.startswith("rtk_")
    await client.close()
    if not accept_task.done():
        accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()


async def test_bad_token_unauthenticated() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"good": "p1"}),
        heartbeat_interval_sec=None,
    )
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="bad",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    with pytest.raises(UnauthenticatedError):
        await client.connect(client_t)
    if not accept_task.done():
        accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()
