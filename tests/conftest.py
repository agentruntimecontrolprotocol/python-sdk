"""Shared pytest fixtures for the ARCP test suite."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from arcp import (
    Capabilities,
    ClientInfo,
    MemoryTransport,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier

# Bound every test by a sane timeout so a stuck await never hangs CI.
pytestmark = pytest.mark.timeout(10)


@pytest.fixture
def memory_pair() -> tuple[MemoryTransport, MemoryTransport]:
    """Return a fresh pair of paired in-memory transports."""
    return pair_memory_transports()


@pytest_asyncio.fixture
async def runtime() -> AsyncIterator[ARCPRuntime]:
    """Default ARCPRuntime with a static bearer (`demo-token` -> principal `p1`)."""
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="test-rt", version="1.1.0"),
        bearer=StaticBearerVerifier({"demo-token": "p1", "other-token": "p2"}),
        heartbeat_interval_sec=None,  # heartbeat off by default in tests
    )
    try:
        yield rt
    finally:
        await rt.close()


@pytest_asyncio.fixture
async def connected_pair(
    runtime: ARCPRuntime,
) -> AsyncIterator[tuple[ARCPClient, asyncio.Task[None]]]:
    """Return a connected (ARCPClient, accept_task) pair via MemoryTransport."""
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(runtime.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="test-client", version="1.0.0"),
        token="demo-token",
        capabilities=Capabilities(features=runtime.capabilities.features),
    )
    await client.connect(client_t)
    try:
        yield client, accept_task
    finally:
        with contextlib.suppress(Exception):
            await client.close()
        if not accept_task.done():
            accept_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await accept_task


@pytest_asyncio.fixture
async def client(
    connected_pair: tuple[ARCPClient, asyncio.Task[None]],
) -> ARCPClient:
    """Return just the connected ARCPClient (the accept task lives in connected_pair)."""
    return connected_pair[0]


@pytest.fixture
def echo_agent() -> Any:
    """Trivial agent that returns whatever was passed in as input."""

    async def _agent(input_value: Any, ctx: Any) -> Any:
        return input_value

    return _agent
