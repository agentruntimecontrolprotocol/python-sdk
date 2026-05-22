"""§9.8.2 — credential rotation status event."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from arcp import Capabilities, ClientInfo, RuntimeInfo, pair_memory_transports
from arcp.client import ARCPClient
from arcp.runtime import (
    ARCPRuntime,
    InMemoryCredentialProvisioner,
    InMemoryRevocationLog,
    JobContext,
    StaticBearerVerifier,
)


async def test_rotate_emits_status_event_and_revokes_prior_value() -> None:
    provisioner = InMemoryCredentialProvisioner()
    subscribed = asyncio.Event()

    async def agent(input_value: Any, ctx: JobContext) -> str:
        await subscribed.wait()
        await ctx.rotate_credential(ctx.credentials[0].id, "rotated-secret")
        return "ok"

    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"a": "p1", "b": "p1"}),
        heartbeat_interval_sec=None,
        credential_provisioner=provisioner,
        revocation_log=InMemoryRevocationLog(),
        job_authorization_policy=lambda ctx: True,
    )
    rt.register_agent("agent", agent)

    async def connect(token: str) -> tuple[ARCPClient, asyncio.Task[None]]:
        server_t, client_t = pair_memory_transports()
        task = asyncio.create_task(rt.accept(server_t))
        client = ARCPClient(
            client=ClientInfo(name="c", version="1"),
            token=token,
            capabilities=Capabilities(features=rt.capabilities.features),
        )
        await client.connect(client_t)
        return client, task

    a, task_a = await connect("a")
    b, task_b = await connect("b")
    try:
        handle = await a.submit(agent="agent", lease_request={"model.use": ["tier-fast/*"]})
        sub = await b.subscribe(handle.job_id)
        subscribed.set()

        submitter_event = await anext(handle.events())
        subscriber_event = await anext(sub.handle.events())

        assert submitter_event["body"] == {
            "phase": "credential_rotated",
            "id": handle.credentials[0].id,
            "value": "rotated-secret",
        }
        assert subscriber_event["body"] == {
            "phase": "credential_rotated",
            "id": handle.credentials[0].id,
        }
        assert handle.credentials[0].id in provisioner.revoked
        await handle.done
    finally:
        for client in (a, b):
            with contextlib.suppress(Exception):
                await client.close()
        for task in (task_a, task_b):
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        await rt.close()
