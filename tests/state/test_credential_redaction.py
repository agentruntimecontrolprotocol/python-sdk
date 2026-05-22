"""§14 — credential values stay out of introspection and log helpers."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from arcp import Capabilities, ClientInfo, RuntimeInfo, pair_memory_transports
from arcp._logger import redact_credentials
from arcp.client import ARCPClient
from arcp.runtime import (
    ARCPRuntime,
    InMemoryCredentialProvisioner,
    InMemoryRevocationLog,
    JobContext,
    StaticBearerVerifier,
)


async def test_cross_principal_list_jobs_omits_credentials() -> None:
    async def agent(input_value: Any, ctx: JobContext) -> str:
        await asyncio.sleep(0.05)
        return "ok"

    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"a": "p1", "b": "p2"}),
        heartbeat_interval_sec=None,
        credential_provisioner=InMemoryCredentialProvisioner(),
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
        jobs = await b.list_jobs()
        dumped = jobs.model_dump(mode="json")
        assert jobs.jobs[0].job_id == handle.job_id
        assert "credentials" not in dumped["jobs"][0]
        assert handle.credentials[0].value not in str(dumped)
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


def test_redact_credentials_strips_nested_values() -> None:
    payload = {
        "payload": {
            "credentials": [
                {"id": "cred_1", "value": "secret", "scheme": "bearer"},
            ]
        }
    }

    redacted = redact_credentials(payload)

    assert redacted["payload"]["credentials"][0]["value"] == "<redacted>"
    assert payload["payload"]["credentials"][0]["value"] == "secret"
