"""Job state machine, heartbeats, cancellation, interrupts (RFC §10)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from arcp.envelope import Envelope
from arcp.errors import ARCPError, ErrorCode
from arcp.messages.execution import (
    JobAcceptedPayload,
    JobCancelledPayload,
    JobCompletedPayload,
    JobFailedPayload,
    JobHeartbeatPayload,
    JobProgressPayload,
    JobStartedPayload,
    JobState,
    ToolErrorPayload,
    ToolResultPayload,
)
from arcp.messages.human import HumanInputRequestPayload
from arcp.messages.streaming import (
    StreamChunkPayload,
    StreamClosePayload,
    StreamErrorPayload,
    StreamKind,
    StreamOpenPayload,
)
from arcp.runtime.stream import StreamManager

logger = structlog.get_logger("arcp.job")

EnvelopeSink = Callable[[Envelope], Awaitable[None]]


def _new_msg_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


def _new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:12]}"




@dataclass
class JobRecord:
    """Per-job runtime bookkeeping."""

    job_id: str
    session_id: str
    state: JobState = "accepted"
    cancellation: asyncio.Event = field(default_factory=asyncio.Event)
    cancellation_deadline_ms: int = 5000
    cancellation_emitted: bool = False
    last_heartbeat: float = 0.0
    heartbeat_sequence: int = 0
    interrupt: asyncio.Event = field(default_factory=asyncio.Event)
    interrupt_prompt: str | None = None
    task: asyncio.Task[Any] | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict[str, Any])
    correlation_id: str | None = None
    trace_id: str | None = None


@dataclass
class JobContext:
    """Tools receive this context to emit progress, streams, and heartbeats."""

    job: JobRecord
    sink: EnvelopeSink
    streams: StreamManager
    heartbeat_interval_seconds: float = 30.0

    async def heartbeat(self, *, deadline_ms: int = 60_000) -> None:
        """Emit a `job.heartbeat` envelope (§10.3)."""

        self.job.heartbeat_sequence += 1
        self.job.last_heartbeat = asyncio.get_running_loop().time()
        envelope = Envelope(
            id=_new_msg_id(),
            type="job.heartbeat",
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            trace_id=self.job.trace_id,
            payload=JobHeartbeatPayload(
                sequence=self.job.heartbeat_sequence,
                deadline_ms=deadline_ms,
                state=self.job.state,
            ).model_dump(),
        )
        await self.sink(envelope)

    async def progress(
        self, *, percent: float | None = None, message: str | None = None
    ) -> None:
        envelope = Envelope(
            id=_new_msg_id(),
            type="job.progress",
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            trace_id=self.job.trace_id,
            payload=JobProgressPayload(percent=percent, message=message).model_dump(
                exclude_none=True
            ),
        )
        await self.sink(envelope)

    async def open_stream(
        self,
        *,
        kind: StreamKind,
        content_type: str | None = None,
        stream_id: str | None = None,
    ) -> str:
        state = self.streams.open(
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            kind=kind,
            content_type=content_type,
            stream_id=stream_id,
        )
        envelope = Envelope(
            id=_new_msg_id(),
            type="stream.open",
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            stream_id=state.stream_id,
            payload=StreamOpenPayload(kind=kind, content_type=content_type).model_dump(
                exclude_none=True
            ),
        )
        await self.sink(envelope)
        return state.stream_id

    async def chunk(
        self,
        stream_id: str,
        *,
        content: Any | None = None,
        data: str | None = None,
        role: str | None = None,
        redacted: bool | None = None,
    ) -> None:
        await self.streams.throttle(stream_id)
        seq = self.streams.next_sequence(stream_id)
        payload = StreamChunkPayload(
            sequence=seq,
            content=content,
            data=data,
            role=role,
            redacted=redacted,
        ).model_dump(exclude_none=True)
        envelope = Envelope(
            id=_new_msg_id(),
            type="stream.chunk",
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            stream_id=stream_id,
            payload=payload,
        )
        await self.sink(envelope)

    async def close_stream(self, stream_id: str, *, reason: str | None = None) -> None:
        self.streams.close(stream_id)
        envelope = Envelope(
            id=_new_msg_id(),
            type="stream.close",
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            stream_id=stream_id,
            payload=StreamClosePayload(reason=reason).model_dump(exclude_none=True),
        )
        await self.sink(envelope)

    async def stream_error(
        self, stream_id: str, *, code: ErrorCode, message: str
    ) -> None:
        self.streams.close(stream_id)
        envelope = Envelope(
            id=_new_msg_id(),
            type="stream.error",
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            stream_id=stream_id,
            payload=StreamErrorPayload(code=str(code), message=message).model_dump(
                exclude_none=True
            ),
        )
        await self.sink(envelope)

    def check_cancel(self) -> None:
        """Raise :class:`ARCPError` ``CANCELLED`` if cancellation has been requested."""

        if self.job.cancellation.is_set():
            raise ARCPError(ErrorCode.CANCELLED, "job cancelled by caller")

    async def request_human_input(
        self,
        *,
        prompt: str,
        response_schema: dict[str, Any] | None = None,
        default: Any | None = None,
        expires_at: str,
    ) -> Envelope:
        """Block the job and emit a ``human.input.request`` (§12.1, §10.5).

        The caller awaits the matching response, which the runtime delivers via
        the session's pending registry. The job's state transitions to
        ``blocked`` for the duration of the await.
        """

        prior_state = self.job.state
        self.job.state = "blocked"
        request_id = _new_msg_id()
        envelope = Envelope(
            id=request_id,
            type="human.input.request",
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            trace_id=self.job.trace_id,
            payload=HumanInputRequestPayload(
                prompt=prompt,
                response_schema=response_schema or {},
                default=default,
                expires_at=expires_at,
            ).model_dump(exclude_none=True),
        )
        # The caller obtains the response via the pending registry — wired by
        # the runtime in Phase 4. For now we return the request envelope so
        # callers can register a future against ``request_id`` via the runtime.
        await self.sink(envelope)
        self.job.state = prior_state
        return envelope


@dataclass
class JobManager:
    """Tracks running jobs and owns their async tasks (§10)."""

    sink: EnvelopeSink
    streams: StreamManager = field(default_factory=StreamManager)
    heartbeat_interval_seconds: float = 30.0
    heartbeat_recovery: str = "fail"
    miss_threshold: int = 2
    _jobs: dict[str, JobRecord] = field(default_factory=dict[str, JobRecord])
    _hard_kill_tasks: set[asyncio.Task[None]] = field(
        default_factory=set[asyncio.Task[None]]
    )

    def get(self, job_id: str) -> JobRecord:
        record = self._jobs.get(job_id)
        if record is None:
            raise ARCPError(ErrorCode.NOT_FOUND, f"job {job_id!r} not found")
        return record

    async def submit(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        impl: Callable[[JobContext, dict[str, Any]], Awaitable[Any]],
        correlation_id: str | None = None,
        trace_id: str | None = None,
    ) -> JobRecord:
        """Accept a tool invocation as a job. Returns the JobRecord."""

        job = JobRecord(
            job_id=_new_job_id(),
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        self._jobs[job.job_id] = job

        await self.sink(
            Envelope(
                id=_new_msg_id(),
                type="job.accepted",
                session_id=session_id,
                job_id=job.job_id,
                correlation_id=correlation_id,
                trace_id=trace_id,
                payload=JobAcceptedPayload(job_id=job.job_id, state="accepted").model_dump(),
            )
        )

        ctx = JobContext(
            job=job,
            sink=self.sink,
            streams=self.streams,
            heartbeat_interval_seconds=self.heartbeat_interval_seconds,
        )
        watchdog = asyncio.create_task(self._watchdog(job))
        job.task = asyncio.create_task(self._run(job, ctx, impl, watchdog))
        return job

    async def _run(
        self,
        job: JobRecord,
        ctx: JobContext,
        impl: Callable[[JobContext, dict[str, Any]], Awaitable[Any]],
        watchdog: asyncio.Task[None],
    ) -> None:
        try:
            job.state = "running"
            job.last_heartbeat = asyncio.get_running_loop().time()
            await self.sink(
                Envelope(
                    id=_new_msg_id(),
                    type="job.started",
                    session_id=job.session_id,
                    job_id=job.job_id,
                    correlation_id=job.correlation_id,
                    trace_id=job.trace_id,
                    payload=JobStartedPayload(job_id=job.job_id).model_dump(),
                )
            )
            assert job.tool_name is not None
            result = await impl(ctx, job.arguments)
            await self._emit_terminal_success(job, result)
        except ARCPError as exc:
            if exc.code == ErrorCode.CANCELLED:
                await self._emit_cancelled(job, reason=exc.message)
            else:
                await self._emit_failed(job, code=exc.code, message=exc.message)
        except asyncio.CancelledError:
            # Hard kill after deadline elapsed.
            if not job.cancellation_emitted:
                try:
                    await self._emit_failed(
                        job, code=ErrorCode.ABORTED, message="job aborted by hard cancel"
                    )
                except Exception as emit_exc:
                    logger.warning(
                        "could not emit ABORTED terminal event",
                        job_id=job.job_id,
                        error=str(emit_exc),
                    )
            return
        except Exception as exc:
            await self._emit_failed(job, code=ErrorCode.INTERNAL, message=str(exc))
        finally:
            watchdog.cancel()
            try:
                await watchdog
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    async def _emit_terminal_success(self, job: JobRecord, result: Any) -> None:
        job.state = "completed"
        await self.sink(
            Envelope(
                id=_new_msg_id(),
                type="tool.result",
                session_id=job.session_id,
                job_id=job.job_id,
                correlation_id=job.correlation_id,
                trace_id=job.trace_id,
                payload=ToolResultPayload(value=result).model_dump(exclude_none=True),
            )
        )
        await self.sink(
            Envelope(
                id=_new_msg_id(),
                type="job.completed",
                session_id=job.session_id,
                job_id=job.job_id,
                correlation_id=job.correlation_id,
                trace_id=job.trace_id,
                payload=JobCompletedPayload(result=result).model_dump(exclude_none=True),
            )
        )

    async def _emit_failed(
        self, job: JobRecord, *, code: ErrorCode, message: str
    ) -> None:
        job.state = "failed"
        await self.sink(
            Envelope(
                id=_new_msg_id(),
                type="tool.error",
                session_id=job.session_id,
                job_id=job.job_id,
                correlation_id=job.correlation_id,
                trace_id=job.trace_id,
                payload=ToolErrorPayload(code=str(code), message=message).model_dump(
                    exclude_none=True
                ),
            )
        )
        await self.sink(
            Envelope(
                id=_new_msg_id(),
                type="job.failed",
                session_id=job.session_id,
                job_id=job.job_id,
                correlation_id=job.correlation_id,
                trace_id=job.trace_id,
                payload=JobFailedPayload(code=str(code), message=message).model_dump(
                    exclude_none=True
                ),
            )
        )

    async def _emit_cancelled(self, job: JobRecord, *, reason: str | None) -> None:
        job.state = "cancelled"
        job.cancellation_emitted = True
        await self.sink(
            Envelope(
                id=_new_msg_id(),
                type="job.cancelled",
                session_id=job.session_id,
                job_id=job.job_id,
                correlation_id=job.correlation_id,
                trace_id=job.trace_id,
                payload=JobCancelledPayload(reason=reason, code=str(ErrorCode.CANCELLED)).model_dump(
                    exclude_none=True
                ),
            )
        )

    async def cancel(self, job_id: str, *, deadline_ms: int = 5000) -> bool:
        """Request cooperative cancellation; returns ``True`` if accepted."""

        job = self.get(job_id)
        if job.state in ("completed", "failed", "cancelled"):
            raise ARCPError(
                ErrorCode.FAILED_PRECONDITION, f"job {job_id!r} is already terminal"
            )
        job.cancellation.set()
        job.cancellation_deadline_ms = deadline_ms

        async def _hard_kill() -> None:
            await asyncio.sleep(deadline_ms / 1000.0)
            if job.state not in ("completed", "failed", "cancelled") and job.task is not None:
                # Terminal state has not been emitted; escalate to ABORTED.
                if not job.cancellation_emitted:
                    await self._emit_failed(
                        job, code=ErrorCode.ABORTED, message="cancellation deadline elapsed"
                    )
                job.task.cancel()

        task = asyncio.create_task(_hard_kill())
        self._hard_kill_tasks.add(task)
        task.add_done_callback(self._hard_kill_tasks.discard)
        return True

    async def interrupt(self, job_id: str, prompt: str) -> None:
        """Request that ``job_id`` pauses and asks for human guidance (§10.5)."""

        job = self.get(job_id)
        if job.state not in ("running", "blocked", "queued"):
            raise ARCPError(
                ErrorCode.FAILED_PRECONDITION, f"job {job_id!r} not interruptible"
            )
        job.interrupt.set()
        job.interrupt_prompt = prompt

    async def _watchdog(self, job: JobRecord) -> None:
        """Per-job heartbeat watchdog (§10.3).

        The watchdog wakes once per heartbeat interval. Each wake checks the
        time elapsed since the last heartbeat: if ``miss_threshold`` consecutive
        intervals pass without one, the job transitions to ``failed`` /
        ``HEARTBEAT_LOST`` (when ``heartbeat_recovery == "fail"``) or
        ``blocked`` (when ``"block"``).
        """

        loop = asyncio.get_running_loop()
        misses = 0
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval_seconds)
                if job.state in ("completed", "failed", "cancelled"):
                    return
                last = job.last_heartbeat or loop.time()
                elapsed = loop.time() - last
                if elapsed > self.heartbeat_interval_seconds:
                    misses += 1
                    if misses >= self.miss_threshold:
                        if self.heartbeat_recovery == "block":
                            job.state = "blocked"
                            misses = 0
                            continue
                        await self._emit_failed(
                            job,
                            code=ErrorCode.HEARTBEAT_LOST,
                            message=f"missed {misses} heartbeats",
                        )
                        if job.task is not None:
                            job.task.cancel()
                        return
                else:
                    misses = 0
        except asyncio.CancelledError:
            return


__all__ = [
    "JobContext",
    "JobManager",
    "JobRecord",
]
