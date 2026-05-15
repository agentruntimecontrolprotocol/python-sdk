"""Feature intersection — client cannot use features outside the negotiated set."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    InvalidRequestError,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_client_without_list_jobs_feature_raises() -> None:
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
        features=("ack", "subscribe"),
        capabilities=Capabilities(features=("ack", "subscribe")),
    )
    await client.connect(client_t)
    assert "list_jobs" not in client.negotiated_features
    with pytest.raises(InvalidRequestError):
        await client.list_jobs()
    await client.close()
    if not accept_task.done():
        accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()
