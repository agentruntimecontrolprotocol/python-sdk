"""Agent execution: timeout, lease watchdog, terminal-event finalization."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .._errors import ARCPError, LeaseExpiredError
from .._messages.execution import JobErrorPayload, JobResultPayload
from .job import Agent, Job, JobContext
from .lease import _parse_iso_utc

if TYPE_CHECKING:
    from .server import ARCPRuntime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


async def run_job(
    runtime: ARCPRuntime,
    job: Job,
    agent_fn: Agent,
    agent_input: Any,
    *,
    max_runtime_sec: int | None,
) -> None:
    """Run an agent under the runtime's concurrency semaphore.

    Owns: state transition, JobContext construction, lease watchdog,
    terminal emit on success/cancel/error.
    """
    async with runtime._semaphore:
        job.state = "running"
        ctx = JobContext(
            job=job,
            signal=asyncio.Event(),
            logger=runtime.logger.bind(job_id=job.job_id),
            chunk_size_cap=runtime.chunk_size_cap,
        )
        watchdog = _start_lease_watchdog(runtime, job)
        try:
            await _invoke_agent(job, agent_fn, agent_input, ctx, max_runtime_sec)
        except asyncio.CancelledError:
            await _finalize_cancelled(job)
            raise
        except Exception as e:
            await _finalize_failure(runtime, job, e)
        finally:
            if watchdog is not None and not watchdog.done():
                watchdog.cancel()
            runtime._job_tasks.pop(job.job_id, None)


def _start_lease_watchdog(runtime: ARCPRuntime, job: Job) -> asyncio.Task[Any] | None:
    lc = job.lease_constraints
    if (
        "lease_expires_at" not in job.session.negotiated_features
        or lc is None
        or lc.expires_at is None
    ):
        return None
    return asyncio.create_task(_lease_watchdog(runtime, job, lc.expires_at))


async def _invoke_agent(
    job: Job,
    agent_fn: Agent,
    agent_input: Any,
    ctx: JobContext,
    max_runtime_sec: int | None,
) -> None:
    if max_runtime_sec is not None:
        async with asyncio.timeout(max_runtime_sec):
            result = await agent_fn(agent_input, ctx)
    else:
        result = await agent_fn(agent_input, ctx)
    if job.state == "running":
        await job.emit_result(
            JobResultPayload(
                final_status="success",
                result=result,
                completed_at=_now_iso(),
            )
        )


async def _finalize_cancelled(job: Job) -> None:
    if job.state != "running":
        return
    await job.emit_result(JobResultPayload(final_status="cancelled", completed_at=_now_iso()))


async def _finalize_failure(runtime: ARCPRuntime, job: Job, exc: BaseException) -> None:
    if isinstance(exc, TimeoutError):
        await job.emit_result(JobResultPayload(final_status="timed_out", completed_at=_now_iso()))
        job.state = "timed_out"
        return
    if isinstance(exc, LeaseExpiredError):
        await job.emit_error(
            JobErrorPayload(
                code=exc.code,
                message=exc.message,
                retryable=False,
                completed_at=_now_iso(),
            )
        )
        return
    if isinstance(exc, ARCPError):
        await job.emit_error(
            JobErrorPayload(
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                completed_at=_now_iso(),
            )
        )
        return
    runtime.logger.exception("agent_failed", job_id=job.job_id)
    await job.emit_error(
        JobErrorPayload(
            code="INTERNAL_ERROR",
            message=str(exc),
            retryable=True,
            completed_at=_now_iso(),
        )
    )


async def _lease_watchdog(runtime: ARCPRuntime, job: Job, expires_at_iso: str) -> None:
    expiry = _parse_iso_utc(expires_at_iso)
    delay = (expiry - datetime.now(UTC)).total_seconds()
    if delay > 0:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
    if job.state != "running":
        return
    await job.emit_error(
        JobErrorPayload(
            code="LEASE_EXPIRED",
            message="lease expired while job was running",
            retryable=False,
            completed_at=_now_iso(),
        )
    )
    task = runtime._job_tasks.get(job.job_id)
    if task is not None:
        task.cancel()


__all__ = ("run_job",)
