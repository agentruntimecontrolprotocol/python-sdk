"""`session.list_jobs` handler with filter / pagination."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from .._envelope import Envelope
from .._errors import InvalidRequestError
from .._messages.session import (
    JobListEntry,
    SessionJobsPayload,
    SessionListJobsPayload,
)
from .._ulid import new_envelope_id
from .job import Job

if TYPE_CHECKING:
    from .server import ARCPRuntime, AuthorizationContext
    from .session import SessionContext


async def handle_list_jobs(runtime: ARCPRuntime, ctx: SessionContext, env: Envelope) -> None:
    from .server import AuthorizationContext

    body = SessionListJobsPayload.model_validate(env.payload)
    limit = body.limit or 100
    offset = int(body.cursor) if body.cursor and body.cursor.isdigit() else 0
    created_after_dt: dt.datetime | None = None
    if body.filter is not None and body.filter.created_after:
        try:
            created_after_dt = dt.datetime.fromisoformat(body.filter.created_after)
        except ValueError as exc:
            raise InvalidRequestError(
                f"filter.created_after is not a valid ISO 8601 timestamp: "
                f"{body.filter.created_after!r}"
            ) from exc
    matching = _filter_jobs(runtime, ctx, body, AuthorizationContext, created_after_dt)
    page = matching[offset : offset + limit]
    next_cursor = str(offset + limit) if offset + limit < len(matching) else None
    entries = tuple(_job_to_entry(j) for j in page)
    payload = SessionJobsPayload(request_id=env.id, jobs=entries, next_cursor=next_cursor)
    out = Envelope(
        id=new_envelope_id(),
        type="session.jobs",
        session_id=ctx.session_id,
        payload=payload.model_dump(mode="json", exclude_none=True),
    )
    ctx.stamp_and_enqueue(out)


def _filter_jobs(
    runtime: ARCPRuntime,
    ctx: SessionContext,
    body: SessionListJobsPayload,
    auth_cls: type[AuthorizationContext],
    created_after_dt: dt.datetime | None,
) -> list[Job]:
    # PLR0913: passes the pre-parsed created_after to avoid re-parsing
    # the ISO string for every job in the loop.
    out: list[Job] = []
    for job in runtime._jobs.values():
        if not runtime.policy(
            auth_cls(requester_principal=ctx.principal, job=job, operation="list")
        ):
            continue
        if not _matches_filter(job, body, created_after_dt):
            continue
        out.append(job)
    return out


def _matches_filter(
    job: Job, body: SessionListJobsPayload, created_after_dt: dt.datetime | None
) -> bool:
    if body.filter is None:
        return True
    if body.filter.status and job.state not in body.filter.status:
        return False
    if body.filter.agent and job.agent_ref != body.filter.agent:
        return False
    return not (created_after_dt is not None and job.submitted_at <= created_after_dt)


def _job_to_entry(j: Job) -> JobListEntry:
    # Credentials are intentionally never echoed from list/introspection surfaces (§14).
    return JobListEntry(
        job_id=j.job_id,
        agent=j.agent_ref,
        status=j.state,
        submitted_at=j.submitted_at.isoformat().replace("+00:00", "Z"),
        parent_job_id=j.parent_job_id,
        trace_id=j.trace_id,
    )


__all__ = ("handle_list_jobs",)
