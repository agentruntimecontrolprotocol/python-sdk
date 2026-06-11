"""#82 — delegated submissions must be a strict subset of the parent (§9.4, §10)."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt

import pytest

from arcp import (
    Capabilities,
    ClientInfo,
    JobNotFoundError,
    LeaseConstraints,
    LeaseSubsetViolationError,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


def _future_iso(hours: int) -> str:
    return (dt.datetime.now(dt.UTC) + dt.timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


async def _connect(rt: ARCPRuntime, token: str = "tok") -> tuple[ARCPClient, asyncio.Task]:
    server_t, client_t = pair_memory_transports()
    task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token=token,
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    await client.connect(client_t)
    return client, task


async def _make_running_parent(rt: ARCPRuntime, client: ARCPClient):
    started = asyncio.Event()

    async def parent_agent(input_value, ctx):
        started.set()
        await asyncio.sleep(30)

    async def child_agent(input_value, ctx):
        return "ok"

    rt.register_agent("parent", parent_agent)
    rt.register_agent("child", child_agent)
    parent = await client.submit(
        agent="parent",
        lease_request={"fs.read": ["/ws/*"], "cost.budget": ["USD:5.00"]},
        lease_constraints=LeaseConstraints(expires_at=_future_iso(2)),
    )
    await asyncio.wait_for(started.wait(), timeout=2.0)
    return parent


async def test_delegation_subset_enforced() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1", "other": "p2"}),
        heartbeat_interval_sec=None,
    )
    client, task = await _connect(rt)
    other, other_task = await _connect(rt, token="other")
    try:
        parent = await _make_running_parent(rt, client)

        # Wider capability than the parent -> LEASE_SUBSET_VIOLATION.
        with pytest.raises(LeaseSubsetViolationError):
            await client.submit(
                agent="child",
                lease_request={"fs.read": ["/ws/**"]},
                parent_job_id=parent.job_id,
            )

        # Budget exceeding the parent's remaining -> LEASE_SUBSET_VIOLATION.
        with pytest.raises(LeaseSubsetViolationError):
            await client.submit(
                agent="child",
                lease_request={"cost.budget": ["USD:10.00"]},
                parent_job_id=parent.job_id,
            )

        # expires_at later than the parent -> LEASE_SUBSET_VIOLATION.
        with pytest.raises(LeaseSubsetViolationError):
            await client.submit(
                agent="child",
                lease_request={"fs.read": ["/ws/sub"]},
                lease_constraints=LeaseConstraints(expires_at=_future_iso(10)),
                parent_job_id=parent.job_id,
            )

        # A genuine subset is accepted.
        child = await client.submit(
            agent="child",
            lease_request={"fs.read": ["/ws/sub"], "cost.budget": ["USD:2.00"]},
            parent_job_id=parent.job_id,
        )
        assert (await asyncio.wait_for(child.done, timeout=2.0)).result == "ok"

        # A foreign principal cannot delegate from a parent it does not own.
        with pytest.raises(JobNotFoundError):
            await other.submit(
                agent="child",
                lease_request={"fs.read": ["/ws/sub"]},
                parent_job_id=parent.job_id,
            )
    finally:
        for c in (client, other):
            with contextlib.suppress(Exception):
                await c.close()
        for t in (task, other_task):
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        await rt.close()
