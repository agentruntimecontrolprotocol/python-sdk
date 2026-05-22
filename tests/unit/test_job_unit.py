"""Unit tests for arcp._runtime.job — Job and JobContext branches."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from arcp._errors import InternalError, InvalidRequestError
from arcp._messages.execution import JobErrorPayload, JobResultPayload, LeaseConstraints
from arcp._runtime.job import Job, JobContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(
    *,
    job_id: str = "job-1",
    agent: str = "echo",
    agent_version: str | None = None,
    lease: dict | None = None,
    lease_constraints: LeaseConstraints | None = None,
    budget: dict | None = None,
    trace_id: str | None = None,
) -> Job:
    session = MagicMock()
    session.session_id = "sess-1"
    session.send = AsyncMock()

    return Job(
        job_id=job_id,
        session=session,
        agent=agent,
        agent_version=agent_version,
        lease=lease if lease is not None else {},
        lease_constraints=lease_constraints,
        budget=dict(budget) if budget else {},
        initial_budget=dict(budget) if budget else {},
        trace_id=trace_id,
    )


def _make_ctx(job: Job | None = None, runtime: MagicMock | None = None) -> JobContext:
    if job is None:
        job = _make_job()
    if runtime is None:
        runtime = MagicMock()
        runtime.credential_provisioner = None
    return JobContext(
        job=job,
        runtime=runtime,
        signal=asyncio.Event(),
        logger=MagicMock(),
    )


def _send_mock(job: Job) -> Any:
    return cast(Any, job.session.send)


# ---------------------------------------------------------------------------
# Job.agent_ref
# ---------------------------------------------------------------------------


async def test_job_agent_ref_without_version() -> None:
    job = _make_job(agent="my-agent", agent_version=None)
    assert job.agent_ref == "my-agent"


async def test_job_agent_ref_with_version() -> None:
    job = _make_job(agent="my-agent", agent_version="1.2.3")
    assert job.agent_ref == "my-agent@1.2.3"


# ---------------------------------------------------------------------------
# Job.apply_cost_metric
# ---------------------------------------------------------------------------


def test_apply_cost_metric_not_cost_prefix_returns_none() -> None:
    job = _make_job(budget={"USD": Decimal("10")})
    result = job.apply_cost_metric("model.tokens", 1.0, "USD")
    assert result is None


def test_apply_cost_metric_no_unit_returns_none() -> None:
    job = _make_job(budget={"USD": Decimal("10")})
    result = job.apply_cost_metric("cost.tokens", 1.0, None)
    assert result is None


def test_apply_cost_metric_negative_value_returns_none() -> None:
    job = _make_job(budget={"USD": Decimal("10")})
    result = job.apply_cost_metric("cost.api", -1.0, "USD")
    assert result is None


def test_apply_cost_metric_unit_not_in_budget_returns_none() -> None:
    job = _make_job(budget={"USD": Decimal("10")})
    result = job.apply_cost_metric("cost.api", 1.0, "EUR")
    assert result is None


def test_apply_cost_metric_valid_decrements() -> None:
    job = _make_job(budget={"USD": Decimal("10")})
    result = job.apply_cost_metric("cost.api", 3.5, "USD")
    assert result == Decimal("6.5")
    assert job.budget["USD"] == Decimal("6.5")


# ---------------------------------------------------------------------------
# Job.should_emit_budget_remaining
# ---------------------------------------------------------------------------


def test_should_emit_budget_remaining_first_call_returns_true() -> None:
    job = _make_job(budget={"USD": Decimal("10")})
    assert job.should_emit_budget_remaining("USD") is True


def test_should_emit_budget_remaining_unchanged_returns_false() -> None:
    job = _make_job(budget={"USD": Decimal("10")})
    job.should_emit_budget_remaining("USD")  # first call sets baseline
    assert job.should_emit_budget_remaining("USD") is False  # unchanged


# ---------------------------------------------------------------------------
# Job.emit_result
# ---------------------------------------------------------------------------


async def test_job_emit_result_sets_success_state() -> None:
    job = _make_job()
    payload = JobResultPayload(final_status="success", completed_at="2024-01-01T00:00:00Z")
    await job.emit_result(payload)
    assert job.state == "success"
    _send_mock(job).assert_awaited_once()


async def test_job_emit_result_non_success_sets_state() -> None:
    job = _make_job()
    payload = JobResultPayload(final_status="cancelled", completed_at="2024-01-01T00:00:00Z")
    await job.emit_result(payload)
    assert job.state == "cancelled"


async def test_job_emit_result_with_inline_sets_flag() -> None:
    job = _make_job()
    payload = JobResultPayload(
        final_status="success", result={"x": 1}, completed_at="2024-01-01T00:00:00Z"
    )
    await job.emit_result(payload)
    assert job.inline_result_emitted is True


async def test_job_emit_result_chunked_and_inline_raises() -> None:
    job = _make_job()
    job.chunked_result_started = True
    payload = JobResultPayload(
        final_status="success", result={"x": 1}, completed_at="2024-01-01T00:00:00Z"
    )
    with pytest.raises(InvalidRequestError, match="MUST NOT mix"):
        await job.emit_result(payload)


# ---------------------------------------------------------------------------
# Job.emit_error
# ---------------------------------------------------------------------------


async def test_job_emit_error_sets_error_state() -> None:
    job = _make_job()
    payload = JobErrorPayload(
        code="INTERNAL_ERROR",
        message="crash",
        retryable=False,
        final_status="error",
        completed_at="2024-01-01T00:00:00Z",
    )
    await job.emit_error(payload)
    assert job.state == "error"
    _send_mock(job).assert_awaited_once()


# ---------------------------------------------------------------------------
# JobContext property accessors
# ---------------------------------------------------------------------------


async def test_ctx_session_id() -> None:
    ctx = _make_ctx()
    assert ctx.session_id == "sess-1"


async def test_ctx_agent_version_none() -> None:
    ctx = _make_ctx()
    assert ctx.agent_version is None


async def test_ctx_agent_ref() -> None:
    ctx = _make_ctx(_make_job(agent="my-agent", agent_version=None))
    assert ctx.agent_ref == "my-agent"


async def test_ctx_lease() -> None:
    ctx = _make_ctx(_make_job(lease={"fs.read": ["*"]}))
    assert ctx.lease == {"fs.read": ["*"]}


async def test_ctx_lease_constraints_none() -> None:
    ctx = _make_ctx()
    assert ctx.lease_constraints is None


async def test_ctx_budget_snapshot() -> None:
    job = _make_job(budget={"USD": Decimal("5")})
    ctx = _make_ctx(job)
    snap = ctx.budget
    snap["USD"] = Decimal("999")  # modifying snapshot must not affect job
    assert ctx.job.budget["USD"] == Decimal("5")


async def test_ctx_credentials_empty() -> None:
    ctx = _make_ctx()
    assert ctx.credentials == ()


async def test_ctx_trace_id_none() -> None:
    ctx = _make_ctx()
    assert ctx.trace_id is None


# ---------------------------------------------------------------------------
# JobContext emitters
# ---------------------------------------------------------------------------


async def test_ctx_log_sends_event() -> None:
    ctx = _make_ctx()
    await ctx.log("info", "hello world")
    _send_mock(ctx.job).assert_awaited_once()


async def test_ctx_log_with_attributes() -> None:
    ctx = _make_ctx()
    await ctx.log("debug", "msg", attributes={"k": "v"})
    _send_mock(ctx.job).assert_awaited_once()


async def test_ctx_thought_sends_event() -> None:
    ctx = _make_ctx()
    await ctx.thought("thinking...")
    _send_mock(ctx.job).assert_awaited_once()


async def test_ctx_status_with_message() -> None:
    ctx = _make_ctx()
    await ctx.status("processing", "step 1")
    _send_mock(ctx.job).assert_awaited_once()


async def test_ctx_status_without_message() -> None:
    ctx = _make_ctx()
    await ctx.status("done")
    _send_mock(ctx.job).assert_awaited_once()


async def test_ctx_progress_minimal() -> None:
    ctx = _make_ctx()
    await ctx.progress(5, total=10, units="items")
    _send_mock(ctx.job).assert_awaited_once()


async def test_ctx_progress_with_message() -> None:
    ctx = _make_ctx()
    await ctx.progress(3, total=10, message="almost there")
    _send_mock(ctx.job).assert_awaited_once()


async def test_ctx_metric_non_cost() -> None:
    """Non-cost metric is emitted without budget decrement."""
    ctx = _make_ctx()
    await ctx.metric({"name": "tokens.used", "value": 100})
    _send_mock(ctx.job).assert_awaited()


async def test_ctx_metric_cost_decrements_budget_and_emits_remaining() -> None:
    """cost.* metric decrements budget and emits budget.remaining event."""
    job = _make_job(
        lease={"cost.budget": ["USD:10"]},
        budget={"USD": Decimal("10")},
    )
    ctx = _make_ctx(job)
    await ctx.metric({"name": "cost.api", "value": 2.0, "unit": "USD"})
    # at least 2 sends: the metric event + the budget.remaining event
    assert _send_mock(job).await_count >= 2
    assert job.budget["USD"] == Decimal("8")


def _chunk_body(data: str = "hello", *, more: bool = False, seq: int = 0) -> dict:
    """Minimal valid result_chunk body with all required fields."""
    return {
        "result_id": "res-1",
        "chunk_seq": seq,
        "data": data,
        "encoding": "utf8",
        "more": more,
    }


async def test_ctx_result_chunk_size_exceeds_cap_raises() -> None:
    ctx = _make_ctx()
    ctx.chunk_size_cap = 5
    with pytest.raises(InternalError, match="size cap"):
        await ctx.result_chunk(_chunk_body("this is longer than 5"))


async def test_ctx_result_chunk_after_inline_result_raises() -> None:
    job = _make_job()
    job.inline_result_emitted = True
    ctx = _make_ctx(job)
    with pytest.raises(InvalidRequestError, match="MUST NOT mix"):
        await ctx.result_chunk(_chunk_body("x"))


async def test_ctx_result_chunk_valid_sets_started_flag() -> None:
    ctx = _make_ctx()
    await ctx.result_chunk(_chunk_body("hello"))
    assert ctx.job.chunked_result_started is True
    _send_mock(ctx.job).assert_awaited_once()


# ---------------------------------------------------------------------------
# JobContext.authorize_model
# ---------------------------------------------------------------------------


async def test_ctx_authorize_model_valid() -> None:
    job = _make_job(lease={"model.use": ["gpt-4*"]})
    ctx = _make_ctx(job)
    ctx.authorize_model("gpt-4-turbo")  # must not raise


async def test_ctx_authorize_model_not_in_lease_raises() -> None:
    from arcp._errors import PermissionDeniedError

    job = _make_job(lease={})
    ctx = _make_ctx(job)
    with pytest.raises(PermissionDeniedError):
        ctx.authorize_model("gpt-4-turbo")


# ---------------------------------------------------------------------------
# JobContext.rotate_credential
# ---------------------------------------------------------------------------


async def test_ctx_rotate_credential_unknown_raises() -> None:
    ctx = _make_ctx()
    with pytest.raises(InvalidRequestError, match="unknown credential id"):
        await ctx.rotate_credential("cred-99", "new-value")
