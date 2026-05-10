"""Permission and lease tests (RFC §15)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from arcp.client.client import ARCPClient
from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode
from arcp.runtime.job import JobContext
from arcp.runtime.server import ARCPRuntime


async def _drain_until(
    client: ARCPClient,
    predicate: Callable[[Envelope], bool],
    *,
    timeout: float = 3.0,
) -> list[Envelope]:
    collected: list[Envelope] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    async for env in client.events():
        collected.append(env)
        if predicate(env):
            return collected
        if loop.time() > deadline:
            raise AssertionError(
                f"timeout; received types: {[e.type for e in collected]}"
            )
    return collected


@pytest.mark.asyncio
async def test_permission_grant_emits_lease_and_resumes(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def writer(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        grant = await ctx.request_permission(
            permission="filesystem.write",
            resource="/tmp/x",
            operation="write",
            requested_lease_seconds=60,
        )
        return {"lease_id": grant["lease_id"]}

    runtime.register_tool("writer", writer)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_w",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "writer", "arguments": {}},
    )
    await client.send(invoke)

    request = await _drain_until(
        client, lambda e: e.type == "permission.request", timeout=2.0
    )
    request_env = request[-1]

    grant = Envelope(
        id="msg_grant",
        type="permission.grant",
        session_id=accepted.session_id,
        correlation_id=request_env.id,
        payload={
            "permission": "filesystem.write",
            "resource": "/tmp/x",
            "operation": "write",
            "lease_seconds": 60,
        },
    )
    await client.send(grant)

    final = await _drain_until(
        client, lambda e: e.type == "job.completed", timeout=3.0
    )
    types = [e.type for e in final]
    assert "lease.granted" in types
    result = next(e for e in final if e.type == "tool.result")
    assert "lease_id" in result.payload["value"]


@pytest.mark.asyncio
async def test_permission_deny_fails_job(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected

    async def writer(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return await ctx.request_permission(
            permission="payment.refund.create",
            resource="ord_4812",
        )

    runtime.register_tool("refunder", writer)
    accepted = await client.open()
    invoke = Envelope(
        id="msg_invoke_r",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "refunder", "arguments": {}},
    )
    await client.send(invoke)
    request = await _drain_until(
        client, lambda e: e.type == "permission.request", timeout=2.0
    )
    deny = Envelope(
        id="msg_deny",
        type="permission.deny",
        session_id=accepted.session_id,
        correlation_id=request[-1].id,
        payload={"permission": "payment.refund.create", "reason": "policy"},
    )
    await client.send(deny)
    final = await _drain_until(
        client, lambda e: e.type == "job.failed", timeout=2.0
    )
    failed = next(e for e in final if e.type == "job.failed")
    assert failed.payload["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_lease_refresh_extends_expiry(
    connected: tuple[ARCPClient, ARCPRuntime, asyncio.Task[None]],
) -> None:
    client, runtime, _ = connected
    accepted = await client.open()

    # Spin up a job that requests a permission, get the lease, then refresh.
    async def writer(ctx: JobContext, args: dict[str, Any]) -> dict[str, Any]:
        return await ctx.request_permission(
            permission="filesystem.write", requested_lease_seconds=10
        )

    runtime.register_tool("granter", writer)
    invoke = Envelope(
        id="msg_invoke_g",
        type="tool.invoke",
        session_id=accepted.session_id,
        payload={"tool": "granter", "arguments": {}},
    )
    await client.send(invoke)
    request = await _drain_until(
        client, lambda e: e.type == "permission.request", timeout=2.0
    )
    grant = Envelope(
        id="msg_grant_l",
        type="permission.grant",
        session_id=accepted.session_id,
        correlation_id=request[-1].id,
        payload={"permission": "filesystem.write", "lease_seconds": 5},
    )
    await client.send(grant)
    completion = await _drain_until(
        client, lambda e: e.type == "lease.granted", timeout=2.0
    )
    lease_env = next(e for e in completion if e.type == "lease.granted")
    lease_id = lease_env.payload["lease_id"]
    original_expiry = lease_env.payload["expires_at"]

    refresh = Envelope(
        id="msg_refresh",
        type="lease.refresh",
        session_id=accepted.session_id,
        payload={"lease_id": lease_id, "extension_seconds": 60},
    )
    extended = await client.request(refresh, timeout=2.0)
    assert extended.type == "lease.extended"
    assert extended.payload["lease_id"] == lease_id
    assert extended.payload["expires_at"] != original_expiry


def test_lease_manager_unit_tests() -> None:
    from arcp.runtime.lease import LeaseManager

    leases = LeaseManager()
    lease = leases.grant(
        permission="x", resource=None, operation=None, seconds=60
    )
    assert leases.assert_valid(lease.lease_id) is lease

    leases.revoke(lease.lease_id, reason="policy")
    with pytest.raises(ARCPError) as exc:
        leases.assert_valid(lease.lease_id)
    assert exc.value.code == ErrorCode.LEASE_REVOKED


def test_lease_expired() -> None:
    from arcp.runtime.lease import LeaseManager

    leases = LeaseManager()
    lease = leases.grant(
        permission="x", resource=None, operation=None, seconds=-1  # already expired
    )
    with pytest.raises(ARCPError) as exc:
        leases.assert_valid(lease.lease_id)
    assert exc.value.code == ErrorCode.LEASE_EXPIRED
