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
from arcp.messages.human import (
    HumanChoiceOption,
    HumanChoiceRequestPayload,
    HumanInputRequestPayload,
)
from arcp.messages.permissions import PermissionRequestPayload
from arcp.messages.streaming import (
    StreamChunkPayload,
    StreamClosePayload,
    StreamErrorPayload,
    StreamKind,
    StreamOpenPayload,
)
from arcp.runtime.pending import PendingRequestRegistry
from arcp.runtime.stream import StreamManager

logger = structlog.get_logger("arcp.job")

EnvelopeSink = Callable[[Envelope], Awaitable[None]]


def _new_msg_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


def _new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:12]}"


def _seconds_until(iso_timestamp: str) -> float:
    """Return seconds from now until ``iso_timestamp`` (RFC 3339, UTC)."""
    from datetime import UTC, datetime

    normalized = (
        iso_timestamp.replace("Z", "+00:00") if iso_timestamp.endswith("Z") else iso_timestamp
    )
    target = datetime.fromisoformat(normalized)
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    return (target - datetime.now(tz=UTC)).total_seconds()


def _ensure_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"value": value}
    return {str(k): v for k, v in value.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


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
    pending: PendingRequestRegistry
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

    async def progress(self, *, percent: float | None = None, message: str | None = None) -> None:
        """Progress."""
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
        """Open stream."""
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
        """Chunk."""
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
        """Close stream."""
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

    async def stream_error(self, stream_id: str, *, code: ErrorCode, message: str) -> None:
        """Stream error."""
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
    ) -> dict[str, Any]:
        """Block the job, emit ``human.input.request``, await response.

        Returns the response payload's ``value`` field. If ``expires_at`` is
        reached before a response arrives and ``default`` is set, the default
        is returned (synthesized as if the response had arrived). Otherwise
        :class:`ARCPError` ``DEADLINE_EXCEEDED`` is raised.
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
        future = self.pending.register(request_id)
        await self.sink(envelope)
        timeout = max(0.0, _seconds_until(expires_at))
        try:
            async with asyncio.timeout(timeout):
                response = await future
        except TimeoutError as exc:
            self.pending.cancel(request_id)
            if default is not None:
                cancelled = Envelope(
                    id=_new_msg_id(),
                    type="human.input.cancelled",
                    session_id=self.job.session_id,
                    job_id=self.job.job_id,
                    correlation_id=request_id,
                    payload={
                        "code": str(ErrorCode.DEADLINE_EXCEEDED),
                        "reason": "deadline elapsed; default applied",
                    },
                )
                await self.sink(cancelled)
                self.job.state = prior_state
                return _ensure_dict(default)
            cancelled = Envelope(
                id=_new_msg_id(),
                type="human.input.cancelled",
                session_id=self.job.session_id,
                job_id=self.job.job_id,
                correlation_id=request_id,
                payload={
                    "code": str(ErrorCode.DEADLINE_EXCEEDED),
                    "reason": "deadline elapsed",
                },
            )
            await self.sink(cancelled)
            self.job.state = prior_state
            raise ARCPError(ErrorCode.DEADLINE_EXCEEDED, "human input request expired") from exc
        self.job.state = prior_state
        return _ensure_dict(response.get("value"))

    async def request_human_choice(
        self,
        *,
        prompt: str,
        options: list[HumanChoiceOption],
        expires_at: str,
        default_choice_id: str | None = None,
    ) -> str:
        """Block the job, emit ``human.choice.request``, await response.

        Returns the chosen option id.
        """
        prior_state = self.job.state
        self.job.state = "blocked"
        request_id = _new_msg_id()
        envelope = Envelope(
            id=request_id,
            type="human.choice.request",
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            trace_id=self.job.trace_id,
            payload=HumanChoiceRequestPayload(
                prompt=prompt,
                options=options,
                expires_at=expires_at,
                default_choice_id=default_choice_id,
            ).model_dump(exclude_none=True),
        )
        future = self.pending.register(request_id)
        await self.sink(envelope)
        timeout = max(0.0, _seconds_until(expires_at))
        try:
            async with asyncio.timeout(timeout):
                response = await future
        except TimeoutError as exc:
            self.pending.cancel(request_id)
            self.job.state = prior_state
            if default_choice_id is not None:
                return default_choice_id
            raise ARCPError(ErrorCode.DEADLINE_EXCEEDED, "human choice request expired") from exc
        self.job.state = prior_state
        choice_id = response.get("choice_id")
        if not isinstance(choice_id, str):
            raise ARCPError(ErrorCode.INVALID_ARGUMENT, "choice response missing choice_id")
        if not any(opt.id == choice_id for opt in options):
            raise ARCPError(
                ErrorCode.INVALID_ARGUMENT,
                f"choice_id {choice_id!r} not in offered options",
            )
        return choice_id

    async def request_permission(
        self,
        *,
        permission: str,
        resource: str | None = None,
        operation: str | None = None,
        reason: str | None = None,
        requested_lease_seconds: int = 300,
    ) -> dict[str, Any]:
        """Block the job, emit ``permission.request``, await grant or deny.

        Returns the response envelope payload (``permission.grant`` or
        ``permission.deny``). Raises :class:`ARCPError` on deny.
        """
        prior_state = self.job.state
        self.job.state = "blocked"
        request_id = _new_msg_id()
        envelope = Envelope(
            id=request_id,
            type="permission.request",
            session_id=self.job.session_id,
            job_id=self.job.job_id,
            trace_id=self.job.trace_id,
            payload=PermissionRequestPayload(
                permission=permission,
                resource=resource,
                operation=operation,
                reason=reason,
                requested_lease_seconds=requested_lease_seconds,
            ).model_dump(exclude_none=True),
        )
        future = self.pending.register(request_id)
        await self.sink(envelope)
        try:
            async with asyncio.timeout(float(requested_lease_seconds)):
                response = await future
        except TimeoutError as exc:
            self.pending.cancel(request_id)
            self.job.state = prior_state
            raise ARCPError(
                ErrorCode.DEADLINE_EXCEEDED,
                "permission request timed out",
            ) from exc
        self.job.state = prior_state
        if response.get("__type__") == "permission.deny":
            raise ARCPError(
                ErrorCode.PERMISSION_DENIED,
                str(response.get("reason") or "permission denied"),
            )
        return response


@dataclass
class JobManager:
    """Tracks running jobs and owns their async tasks (§10)."""

    sink: EnvelopeSink
    streams: StreamManager = field(default_factory=StreamManager)
    pending: PendingRequestRegistry = field(default_factory=PendingRequestRegistry)
    heartbeat_interval_seconds: float = 30.0
    heartbeat_recovery: str = "fail"
    miss_threshold: int = 2
    _jobs: dict[str, JobRecord] = field(default_factory=dict[str, JobRecord])
    _hard_kill_tasks: set[asyncio.Task[None]] = field(default_factory=set[asyncio.Task[None]])

    def get(self, job_id: str) -> JobRecord:
        """Get."""
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
            pending=self.pending,
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

    async def _emit_failed(self, job: JobRecord, *, code: ErrorCode, message: str) -> None:
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
                payload=JobCancelledPayload(
                    reason=reason, code=str(ErrorCode.CANCELLED)
                ).model_dump(exclude_none=True),
            )
        )

    async def cancel(self, job_id: str, *, deadline_ms: int = 5000) -> bool:
        """Request cooperative cancellation; returns ``True`` if accepted."""
        job = self.get(job_id)
        if job.state in ("completed", "failed", "cancelled"):
            raise ARCPError(ErrorCode.FAILED_PRECONDITION, f"job {job_id!r} is already terminal")
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
            raise ARCPError(ErrorCode.FAILED_PRECONDITION, f"job {job_id!r} not interruptible")
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
