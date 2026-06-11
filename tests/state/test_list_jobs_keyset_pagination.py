"""#77 — session.list_jobs uses a keyset cursor and bounds page materialization."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, cast

from arcp import (
    Capabilities,
    ClientInfo,
    RuntimeInfo,
    pair_memory_transports,
)
from arcp._envelope import Envelope
from arcp._messages.session import SessionListJobsPayload
from arcp._runtime import _handler_list_jobs
from arcp._runtime.job import Job
from arcp._ulid import new_envelope_id, new_job_id
from arcp.client import ARCPClient
from arcp.runtime import ARCPRuntime, StaticBearerVerifier


def _make_job(principal: str) -> Job:
    return Job(
        job_id=new_job_id(),
        session=cast(Any, None),
        agent="a",
        agent_version=None,
        lease={},
        lease_constraints=None,
        budget={},
        initial_budget={},
        submitter_principal=principal,
        state="running",
    )


async def _list_once(
    rt: ARCPRuntime, ctx: Any, *, limit: int, cursor: str | None
) -> tuple[list[str], str | None]:
    from arcp._runtime._handlers import handle_list_jobs

    while not ctx._send_queue.empty():
        ctx._send_queue.get_nowait()
    env = Envelope(
        id=new_envelope_id(),
        type="session.list_jobs",
        session_id=ctx.session_id,
        payload=SessionListJobsPayload(limit=limit, cursor=cursor).model_dump(
            mode="json", exclude_none=True
        ),
    )
    await handle_list_jobs(rt, ctx, env)
    job_ids: list[str] = []
    next_cursor: str | None = None
    while not ctx._send_queue.empty():
        item = ctx._send_queue.get_nowait()
        if item is not None and item.type == "session.jobs":
            job_ids = [j["job_id"] for j in item.payload.get("jobs", [])]
            next_cursor = item.payload.get("next_cursor")
    return job_ids, next_cursor


async def test_keyset_pagination_bounds_materialization_and_visits_all() -> None:
    rt = ARCPRuntime(
        runtime=RuntimeInfo(name="r", version="1"),
        bearer=StaticBearerVerifier({"tok": "p1"}),
        heartbeat_interval_sec=None,
        job_authorization_policy=lambda ctx: True,
    )
    server_t, client_t = pair_memory_transports()
    accept_task = asyncio.create_task(rt.accept(server_t))
    client = ARCPClient(
        client=ClientInfo(name="c", version="1"),
        token="tok",
        capabilities=Capabilities(features=rt.capabilities.features),
    )
    welcome = await client.connect(client_t)
    ctx = rt._sessions[welcome.session_id]

    total = 250
    for _ in range(total):
        job = _make_job("p1")
        rt._jobs[job.job_id] = job
    all_ids = list(rt._jobs.keys())

    # Count how many JobListEntry objects get materialized per request.
    real_to_entry = _handler_list_jobs._job_to_entry
    calls: dict[str, int] = {"max_per_page": 0}

    def _counting(job: Job) -> Any:
        calls["max_per_page"] += 1
        return real_to_entry(job)

    _handler_list_jobs._job_to_entry = _counting  # type: ignore[assignment]
    try:
        limit = 10
        seen: list[str] = []
        cursor: str | None = None
        pages = 0
        while True:
            calls["max_per_page"] = 0
            page, cursor = await _list_once(rt, ctx, limit=limit, cursor=cursor)
            # Materialization per request is bounded by `limit` (no full scan).
            assert calls["max_per_page"] <= limit
            assert len(page) <= limit
            seen.extend(page)
            pages += 1
            if cursor is None:
                break
            # A non-null cursor is a keyset job_id, not a numeric offset.
            assert cursor.startswith("job_")
            assert pages <= total  # guard against an infinite loop
    finally:
        _handler_list_jobs._job_to_entry = real_to_entry  # type: ignore[assignment]

    # Every job is visited exactly once, in stable job_id order.
    assert seen == all_ids
    assert len(set(seen)) == total

    await client.close()
    accept_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await accept_task
    await rt.close()
