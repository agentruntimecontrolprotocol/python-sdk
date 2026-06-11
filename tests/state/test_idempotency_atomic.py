"""#86 — concurrent same-key submits across sessions create exactly one job (§7.2)."""

from __future__ import annotations

import asyncio
import contextlib

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._runtime.credentials import (
    Credential,
    CredentialConstraints,
    InMemoryRevocationLog,
    JobCredentialContext,
)
from arcp._messages.execution import Lease
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


class _SlowProvisioner:
    """Provisioner whose issue() suspends, widening the check-and-store race."""

    def __init__(self) -> None:
        self.issue_count = 0
        self.revoked: list[str] = []

    async def issue(self, lease: Lease, ctx: JobCredentialContext) -> tuple[Credential, ...]:
        self.issue_count += 1
        await asyncio.sleep(0.05)  # suspension point that exposes the race
        return (
            Credential(
                id=f"cred_{ctx.job_id}",
                scheme="bearer",
                value="tok",
                endpoint="https://gw.example/v1",
                profile="test",
                constraints=CredentialConstraints(),
            ),
        )

    async def revoke(self, credential_id: str) -> None:
        self.revoked.append(credential_id)


async def _connect(rt: ARCPRuntime) -> tuple[ARCPClient, asyncio.Task]:
    server_t, client_t = pair_memory_transports()
    task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",  # same token => same principal
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await client.connect(client_t)
    return client, task


async def test_concurrent_same_key_submits_one_job_one_issue() -> None:
    provisioner = _SlowProvisioner()
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
        credential_provisioner=provisioner,
        revocation_log=InMemoryRevocationLog(),
    )

    async def agent(input_value, ctx):
        return "ok"

    rt.register_agent("a", agent)

    # Two independent sessions for the *same* principal, each with its own
    # read pump — the concurrency the atomicity fix must guard.
    c1, t1 = await _connect(rt)
    c2, t2 = await _connect(rt)
    try:
        key = "dup-key"
        h1, h2 = await asyncio.gather(
            c1.submit(agent="a", input=1, idempotency_key=key, lease_request={"model.use": ["m/*"]}),
            c2.submit(agent="a", input=1, idempotency_key=key, lease_request={"model.use": ["m/*"]}),
        )
        # Exactly one job and one credential issuance for the reused key.
        assert h1.job_id == h2.job_id
        assert provisioner.issue_count == 1
    finally:
        for c in (c1, c2):
            with contextlib.suppress(Exception):
                await c.close()
        for t in (t1, t2):
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        await rt.close()
