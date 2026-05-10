"""Shared helpers for examples — spin up an in-process runtime + client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from arcp.auth.bearer import StaticTokenValidator
from arcp.client.client import ARCPClient
from arcp.messages.session import AuthBlock, Capabilities, Identity, RuntimeIdentity
from arcp.runtime.server import ARCPRuntime, RuntimeConfig
from arcp.transport.in_memory import create_pair


def _advertised() -> Capabilities:
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


@asynccontextmanager
async def runtime_and_client() -> AsyncIterator[tuple[ARCPRuntime, ARCPClient]]:
    rt = ARCPRuntime(
        config=RuntimeConfig(
            runtime_identity=RuntimeIdentity(kind="arcp-py-example", version="0.1.0"),
            advertised_capabilities=_advertised(),
            bearer_validator=StaticTokenValidator({"demo": "alice"}),
        )
    )
    await rt.start()
    client_t, server_t = create_pair()
    server_task = asyncio.create_task(rt.serve_session(server_t))
    client = ARCPClient(
        transport=client_t,
        client_identity=Identity(kind="arcp-py-example", version="0.1.0"),
        auth=AuthBlock(scheme="bearer", token="demo"),
        capabilities=Capabilities(
            streaming=True,
            human_input=True,
            artifacts=True,
            subscriptions=True,
        ),
    )
    try:
        yield rt, client
    finally:
        await client.close()
        server_task.cancel()
        with suppress(BaseException):
            await server_task
        await rt.close()
