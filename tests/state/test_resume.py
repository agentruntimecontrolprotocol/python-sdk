"""§6.2 — resume token rotates between sessions."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


async def test_resume_token_rotates_across_connections() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"t": "p1"}),
        heartbeat_interval_sec=None,
    )
    tokens: list[str] = []
    accept_tasks: list[asyncio.Task] = []
    for _ in range(2):
        server_t, client_t = pair_memory_transports()
        accept_tasks.append(asyncio.create_task(rt.accept(server_t)))
        c = ARCPClient(
            client=ClientInfo(name="c", version="1"),
            token="t",
            capabilities=Capabilities(features=rt.capabilities.features),
        )
        w = await c.connect(client_t)
        tokens.append(w.resume_token)
        await c.close()
    for t in accept_tasks:
        if not t.done():
            t.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
    assert tokens[0] != tokens[1]
    await rt.close()


@pytest.mark.skip(reason="Full resume replay not yet implemented end-to-end via client")
async def test_resume_replay_events() -> None:
    pass
