"""`session.list_jobs` handler with filter / pagination."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .._envelope import Envelope
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
    matching = _filter_jobs(runtime, ctx, body, AuthorizationContext)
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
) -> list[Job]:
    out: list[Job] = []
    for job in runtime._jobs.values():
        if not runtime.policy(
            auth_cls(requester_principal=ctx.principal, job=job, operation="list")
        ):
            continue
        if not _matches_filter(job, body):
            continue
        out.append(job)
    return out


def _matches_filter(job: Job, body: SessionListJobsPayload) -> bool:
    if body.filter is None:
        return True
    if body.filter.status and job.state not in body.filter.status:
        return False
    if body.filter.agent and job.agent_ref != body.filter.agent:
        return False
    if body.filter.created_after:
        cutoff = datetime.fromisoformat(body.filter.created_after.replace("Z", "+00:00"))
        if job.submitted_at <= cutoff:
            return False
    return True


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
