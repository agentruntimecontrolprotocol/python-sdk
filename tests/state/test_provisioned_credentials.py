"""§9.8 — issue, expose to submitter, and revoke provisioned credentials."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from arcp import (
    ARCPCancelledError,
    ARCPTimeoutError,
    Capabilities,
    ClientInfo,
    InternalError,
    InvalidRequestError,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import (
    ARCPRuntime,
    InMemoryCredentialProvisioner,
    InMemoryRevocationLog,
    JobContext,
    StaticBearerVerifier,
)


async def _connect(
    rt: ARCPRuntime,
    *,
    token: str = "tok",
) -> tuple[ARCPClient, asyncio.Task[None]]:
    server_t, client_t = pair_memory_transports()
    task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token=token,
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await client.connect(client_t)
    return client, task


async def _close(rt: ARCPRuntime, *items: tuple[ARCPClient, asyncio.Task[None]]) -> None:
    for client, _task in items:
        with contextlib.suppress(Exception):
            await client.close()
    for _client, task in items:
        if not task.done():
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
    await rt.close()


async def _wait_for(predicate: Callable[[], bool]) -> None:
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met")


def _runtime_with_credentials(
    agent: Callable[[Any, JobContext], Awaitable[Any]],
) -> tuple[ARCPRuntime, InMemoryCredentialProvisioner, InMemoryRevocationLog]:
    provisioner = InMemoryCredentialProvisioner()
    revocations = InMemoryRevocationLog()
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
        credential_provisioner=provisioner,
        revocation_log=revocations,
    )
    rt.register_agent("agent", agent)
    return rt, provisioner, revocations


async def test_job_accepted_carries_credentials() -> None:
    async def agent(input_value: Any, ctx: JobContext) -> str:
        return "ok"

    rt, provisioner, _revocations = _runtime_with_credentials(agent)
    client, task = await _connect(rt)
    try:
        handle = await client.submit(
            agent="agent",
            lease_request={"cost.budget": ["USD:5.00"], "model.use": ["tier-fast/*"]},
        )
        credential = handle.credentials[0]
        assert credential.id.startswith("cred_job_")
        assert credential.scheme == "bearer"
        assert credential.endpoint == "https://gateway.example.test/v1"
        assert credential.constraints is not None
        assert credential.constraints.cost_budget == ("USD:5.00",)
        assert credential.constraints.model_use == ("tier-fast/*",)
        assert provisioner.issued[0].id == credential.id
        await handle.done
    finally:
        await _close(rt, (client, task))


@pytest.mark.parametrize("mode", ["success", "error", "cancelled", "timed_out"])
async def test_revoke_called_on_terminal_states(mode: str) -> None:
    async def agent(input_value: Any, ctx: JobContext) -> str:
        if mode == "error":
            raise RuntimeError("boom")
        if mode in {"cancelled", "timed_out"}:
            await asyncio.sleep(2)
        return "ok"

    rt, provisioner, revocations = _runtime_with_credentials(agent)
    client, task = await _connect(rt)
    try:
        handle = await client.submit(
            agent="agent",
            lease_request={"model.use": ["tier-fast/*"]},
            max_runtime_sec=1 if mode == "timed_out" else None,
        )
        if mode == "cancelled":
            await client.cancel_job(handle.job_id)
        # §7.4/§12: cancellation and timeout are terminal job.error envelopes,
        # so awaiting the handle raises the mapped error.
        expected_exc: type[Exception] | None = {
            "error": InternalError,
            "cancelled": ARCPCancelledError,
            "timed_out": ARCPTimeoutError,
        }.get(mode)
        if expected_exc is not None:
            with pytest.raises(expected_exc):
                await handle.done
        else:
            await handle.done
        cred_id = handle.credentials[0].id
        await _wait_for(lambda: cred_id in provisioner.revoked)
        assert (handle.job_id, cred_id) not in await revocations.outstanding()
    finally:
        await _close(rt, (client, task))


async def test_construct_without_revocation_log_raises() -> None:
    with pytest.raises(InvalidRequestError):
        ARCPRuntime(
            runtime=RuntimeInfo(name="r", version="1"),
            bearer=StaticBearerVerifier({"tok": "p1"}),
            credential_provisioner=InMemoryCredentialProvisioner(),
        )


async def test_advertises_features_only_when_configured() -> None:
    bare = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )
    provisioned = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
        credential_provisioner=InMemoryCredentialProvisioner(),
        revocation_log=InMemoryRevocationLog(),
    )
    try:
        # provisioned_credentials (§9.8) is gated on a configured provisioner.
        assert "provisioned_credentials" not in bare.capabilities.features
        assert "provisioned_credentials" in provisioned.capabilities.features
        # model.use (§9.7) negotiates independently and is advertised by both
        # a provisioner-less runtime and a provisioned one (#69).
        assert "model.use" in bare.capabilities.features
        assert "model.use" in provisioned.capabilities.features
    finally:
        await bare.close()
        await provisioned.close()


async def test_default_client_and_bare_runtime_negotiate_model_use() -> None:
    """#69: model.use is negotiated without a credential provisioner."""
    import asyncio
    import contextlib

    from arcp import ClientInfo, pair_memory_transports
    from arcp.client import ARCPClient

    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
    )
    server_t, client_t = pair_memory_transports()
    task = asyncio.create_task(rt.accept(server_t))
    # Default client capabilities (all v1.1 features).
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
    )
    try:
        await client.connect(client_t)
        assert client.has_feature("model.use")
        assert not client.has_feature("provisioned_credentials")
    finally:
        with contextlib.suppress(Exception):
            await client.close()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        await rt.close()
