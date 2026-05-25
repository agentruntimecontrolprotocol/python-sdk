"""Job state machine, JobContext (agent surface), result-stream writer."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
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
    from .credentials import Credential
    from .server import ARCPRuntime
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
    credentials: tuple[Credential, ...] = ()
    state: JobStateName = "pending"
    chunked_result_started: bool = False
    inline_result_emitted: bool = False
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    idempotency_key: str | None = None
    # Wire dict of the most-recent terminal envelope (job.result / job.error)
    # this job emitted; used by the idempotency store to replay terminals on
    # duplicate submissions arriving after completion.
    last_terminal_envelope: dict[str, Any] | None = None
    _last_budget_emit: dict[str, Decimal] = field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]

    @property
    def agent_ref(self) -> str:
        return f"{self.agent}@{self.agent_version}" if self.agent_version else self.agent

    def apply_cost_metric(
        self, name: str, value: Decimal | float | int | str, unit: str | None
    ) -> Decimal | None:
        """Decrement the per-currency counter and return the new remaining (or None).

        Accepts `value` as `Decimal | int | float | str` so callers can preserve
        decimal precision through the budget arithmetic. Non-numeric strings
        raise `ValueError`.
        """
        if not name.startswith("cost.") or unit is None:
            return None
        delta = value if isinstance(value, Decimal) else Decimal(str(value))
        if delta < 0:
            # spec §9.6: negative metrics MUST NOT decrement
            return None
        if unit not in self.budget:
            return None
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
        # Note: `_finalize_failure`/`_finalize_cancelled` on the runner own
        # the non-success transitions and may overwrite `state` after this.
        self.state = payload.final_status
        if payload.result is not None:
            self.inline_result_emitted = True
        # Stamp the terminal envelope *before* dispatching so any duplicate
        # idempotent submit that races behind the write pump can replay it.
        self.last_terminal_envelope = env.to_wire()
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
        # Stamp before dispatch (see emit_result note).
        self.last_terminal_envelope = env.to_wire()
        await self.session.send(env)


@dataclass
class JobContext:
    """The async surface an agent coroutine sees."""

    job: Job
    runtime: ARCPRuntime
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
    def credentials(self) -> tuple[Credential, ...]:
        return self.job.credentials

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
        # Normalize the value once with Decimal precision so the budget
        # arithmetic does not lose precision through a float round-trip.
        raw_value = body.get("value", 0)
        try:
            normalized = raw_value if isinstance(raw_value, Decimal) else Decimal(str(raw_value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("metric.value must be a number or numeric string") from exc
        # Rewrite the body so downstream validation and the wire payload see a
        # canonical JSON number (the spec wire format is a JSON number for
        # metric.value; precision is preserved by the Decimal path above and
        # by Job.budget which already holds Decimal counters).
        body = {**body, "value": float(normalized)}
        validate_metric_body(body)
        name = str(body.get("name", ""))
        unit = body.get("unit") if isinstance(body.get("unit"), str) else None
        remaining = self.job.apply_cost_metric(name, normalized, unit)
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

    def authorize_model(self, model_id: str, *, now: datetime | None = None) -> None:
        """Authorize an upstream model id against the job's `model.use` lease."""
        validate_lease_op(
            self.lease,
            LeaseOpContext(capability="model.use", target=model_id, now=now),
            constraints=self.lease_constraints,
        )

    async def rotate_credential(self, credential_id: str, new_value: str) -> None:
        """Publish a rotated credential value and revoke the prior credential promptly."""
        prior = next((cred for cred in self.job.credentials if cred.id == credential_id), None)
        if prior is None:
            raise InvalidRequestError(f"unknown credential id: {credential_id}")
        await self.job.emit_event(
            "status",
            {"phase": "credential_rotated", "id": credential_id, "value": new_value},
        )
        self.job.credentials = tuple(
            replace(cred, value=new_value) if cred.id == credential_id else cred
            for cred in self.job.credentials
        )
        if self.runtime.credential_provisioner is not None:
            await self.runtime.credential_provisioner.revoke(prior.id)


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
