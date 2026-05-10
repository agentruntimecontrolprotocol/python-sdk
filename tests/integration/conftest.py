"""Integration test fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from arcp.auth.bearer import StaticTokenValidator
from arcp.client.client import ARCPClient
from arcp.messages.session import AuthBlock, Capabilities, Identity, RuntimeIdentity
from arcp.runtime.server import ARCPRuntime, RuntimeConfig
from arcp.transport.in_memory import create_pair


def default_advertised() -> Capabilities:
    return Capabilities(
        streaming=True,
        durable_jobs=True,
        binary_streams=True,
        binary_encoding=["base64"],
        human_input=True,
        artifacts=True,
        subscriptions=True,
        interrupt=True,
        anonymous=False,
        heartbeat_interval_seconds=30,
        heartbeat_recovery="fail",
    )


@pytest.fixture
async def runtime() -> AsyncIterator[ARCPRuntime]:
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(
                kind="reference",
                version="0.1.0",
                trust_level="trusted",
            ),
            advertised_capabilities=default_advertised(),
            bearer_validator=StaticTokenValidator({"good-token": "alice"}),
        )
    )
    await rt.start()
    try:
        yield rt
    finally:
        await rt.close()


@pytest.fixture
async def connected(
    runtime: ARCPRuntime,
) -> AsyncIterator[tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]]]:
    """Spin up a runtime + client connected by an in-memory transport pair."""

    client_t, server_t = create_pair()
    server_task = asyncio.create_task(runtime.serve_session(server_t))
    client = ARCPClient(
        transport=client_t,
        client_identity=Identity(kind="reference-test", version="0.1.0"),
        auth=AuthBlock(scheme="bearer", token="good-token"),
        capabilities=Capabilities(streaming=True, human_input=True, artifacts=True),
    )
    try:
        yield client, runtime, server_task
    finally:
        await client.close()
        server_task.cancel()
        try:
            await server_task
        except BaseException:
            pass
