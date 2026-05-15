"""Job state machine, JobContext (agent surface), result-stream writer."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from .._envelope import Envelope
from .._errors import InternalError, InvalidRequestError
from .._logger import get_logger
from .._messages.execution import (
    JobErrorPayload,
    JobResultPayload,
    Lease,
    LeaseConstraints,
    validate_metric_body,
    validate_progress_body,
    validate_result_chunk_body,
)
from .._ulid import new_envelope_id, new_result_id
from .lease import LeaseOpContext, validate_lease_op

if TYPE_CHECKING:
    from .session import SessionContext

_LOG = get_logger("arcp.runtime.job")

JobStateName = Literal["pending", "running", "success", "error", "cancelled", "timed_out"]
LogLevel = Literal["debug", "info", "warn", "error"]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class Job:
    """Server-side job record. Owns its event-emit funnel + budget state."""

    job_id: str
    session: SessionContext
    agent: str
    agent_version: str | None
    lease: Lease
    lease_constraints: LeaseConstraints | None
    budget: dict[str, Decimal]
    initial_budget: dict[str, Decimal]
    parent_job_id: str | None = None
    delegate_id: str | None = None
    trace_id: str | None = None
    submitter_principal: str | None = None
    state: JobStateName = "pending"
    chunked_result_started: bool = False
    inline_result_emitted: bool = False
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _last_budget_emit: dict[str, Decimal] = field(default_factory=dict)

    @property
    def agent_ref(self) -> str:
        return f"{self.agent}@{self.agent_version}" if self.agent_version else self.agent

    def apply_cost_metric(self, name: str, value: float, unit: str | None) -> Decimal | None:
        """Decrement the per-currency counter and return the new remaining (or None)."""
        if not name.startswith("cost.") or unit is None:
            return None
        if value < 0:
            # spec §9.6: negative metrics MUST NOT decrement
            return None
        if unit not in self.budget:
            return None
        delta = Decimal(str(value))
        self.budget[unit] = self.budget[unit] - delta
        return self.budget[unit]

    def should_emit_budget_remaining(self, currency: str) -> bool:
        last = self._last_budget_emit.get(currency)
        cur = self.budget.get(currency, Decimal("0"))
        if last is None or abs(last - cur) >= Decimal("0.0001"):
            self._last_budget_emit[currency] = cur
            return True
        return False

    async def emit_event(self, kind: str, body: dict[str, Any], *, ts: str | None = None) -> None:
        env = Envelope(
            id=new_envelope_id(),
            type="job.event",
            session_id=self.session.session_id,
            job_id=self.job_id,
            trace_id=self.trace_id,
            payload={"kind": kind, "ts": ts or _now_iso(), "body": body},
        )
        await self.session.send(env)

    async def emit_result(self, payload: JobResultPayload) -> None:
        if self.chunked_result_started and payload.result is not None:
            raise InvalidRequestError(
                "MUST NOT mix inline result and result_chunk in one job (§8.4)"
            )
        env = Envelope(
            id=new_envelope_id(),
            type="job.result",
            session_id=self.session.session_id,
            job_id=self.job_id,
            trace_id=self.trace_id,
            payload=payload.model_dump(mode="json", exclude_none=True),
        )
        self.state = payload.final_status if payload.final_status != "success" else "success"
        if payload.result is not None:
            self.inline_result_emitted = True
        await self.session.send(env)

    async def emit_error(self, payload: JobErrorPayload) -> None:
        env = Envelope(
            id=new_envelope_id(),
            type="job.error",
            session_id=self.session.session_id,
            job_id=self.job_id,
            trace_id=self.trace_id,
            payload=payload.model_dump(mode="json", exclude_none=True),
        )
        self.state = "error"
        await self.session.send(env)


@dataclass
class JobContext:
    """The async surface an agent coroutine sees."""

    job: Job
    signal: asyncio.Event
    logger: Any
    chunk_size_cap: int = 1024 * 1024  # §14 SHOULD cap

    # ---- identity helpers -------------------------------------------------
    @property
    def job_id(self) -> str:
        return self.job.job_id

    @property
    def session_id(self) -> str:
        return self.job.session.session_id

    @property
    def agent(self) -> str:
        return self.job.agent

    @property
    def agent_version(self) -> str | None:
        return self.job.agent_version

    @property
    def agent_ref(self) -> str:
        return self.job.agent_ref

    @property
    def lease(self) -> Lease:
        return self.job.lease

    @property
    def lease_constraints(self) -> LeaseConstraints | None:
        return self.job.lease_constraints

    @property
    def budget(self) -> dict[str, Decimal]:
        # Read-only snapshot.
        return dict(self.job.budget)

    @property
    def trace_id(self) -> str | None:
        return self.job.trace_id

    # ---- event-kind emitters ---------------------------------------------
    async def log(
        self,
        level: LogLevel,
        message: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        body: dict[str, Any] = {"level": level, "message": message}
        if attributes:
            body["attributes"] = attributes
        await self.job.emit_event("log", body)

    async def thought(self, text: str) -> None:
        await self.job.emit_event("thought", {"text": text})

    async def status(self, phase: str, message: str | None = None) -> None:
        body: dict[str, Any] = {"phase": phase}
        if message is not None:
            body["message"] = message
        await self.job.emit_event("status", body)

    async def metric(self, body: dict[str, Any]) -> None:
        validate_metric_body(body)
        # Apply cost decrement before emission so a follow-up budget snapshot is fresh.
        name = str(body.get("name", ""))
        value = float(body.get("value", 0))
        unit = body.get("unit") if isinstance(body.get("unit"), str) else None
        remaining = self.job.apply_cost_metric(name, value, unit)
        await self.job.emit_event("metric", body)
        if (
            remaining is not None
            and unit is not None
            and self.job.should_emit_budget_remaining(unit)
        ):
            await self.job.emit_event(
                "metric",
                {
                    "name": "cost.budget.remaining",
                    "value": float(remaining),
                    "unit": unit,
                },
            )

    async def tool_call(self, body: dict[str, Any]) -> None:
        await self.job.emit_event("tool_call", body)

    async def tool_result(self, body: dict[str, Any]) -> None:
        await self.job.emit_event("tool_result", body)

    async def progress(
        self,
        current: int,
        *,
        total: int | None = None,
        units: str | None = None,
        message: str | None = None,
    ) -> None:
        body: dict[str, Any] = {"current": current}
        if total is not None:
            body["total"] = total
        if units is not None:
            body["units"] = units
        if message is not None:
            body["message"] = message
        validate_progress_body(body)
        await self.job.emit_event("progress", body)

    async def result_chunk(self, body: dict[str, Any]) -> None:
        validate_result_chunk_body(body)
        size = len(body.get("data", "").encode("utf-8"))
        if size > self.chunk_size_cap:
            raise InternalError(
                f"result_chunk data exceeds size cap ({size} > {self.chunk_size_cap})"
            )
        if self.job.inline_result_emitted:
            raise InvalidRequestError(
                "MUST NOT mix inline result and result_chunk in one job (§8.4)"
            )
        self.job.chunked_result_started = True
        await self.job.emit_event("result_chunk", body)

    def stream_result(self, *, result_id: str | None = None) -> ResultStream:
        """Open a streamed-result writer; finalize with `await stream.close(...)`."""
        return ResultStream(self, result_id=result_id or new_result_id())

    # ---- lease op authorization (test seam) ------------------------------
    def authorize(
        self,
        capability: str,
        target: str,
        *,
        cost: dict[str, Decimal] | None = None,
        now: datetime | None = None,
    ) -> None:
        validate_lease_op(
            self.lease,
            LeaseOpContext(capability=capability, target=target, cost=cost, now=now),
            constraints=self.lease_constraints,
            budget=self.job.budget if "cost.budget" in self.lease else None,
        )


# ---- agent type alias ----------------------------------------------------

from .result_stream import ResultStream  # noqa: E402

Agent = Callable[[Any, JobContext], Awaitable[Any]]


__all__ = (
    "Agent",
    "Job",
    "JobContext",
    "JobStateName",
    "LogLevel",
    "ResultStream",
)
