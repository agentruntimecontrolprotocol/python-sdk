"""Job-level message payloads, lease + budget helpers (spec §7–§9)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .event_bodies import (
    EVENT_KINDS,
    ArtifactRefBody,
    DelegateBody,
    LogBody,
    MetricBody,
    ProgressBody,
    ResultChunkBody,
    StatusBody,
    ThoughtBody,
    ToolCallBody,
    ToolResultBody,
    validate_metric_body,
    validate_progress_body,
    validate_result_chunk_body,
)

_AGENT_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9._-]*$")
_AGENT_VERSION_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def parse_agent_ref(ref: str) -> tuple[str, str | None]:
    """Parse `name` or `name@version`; raise `ValueError` on malformed input."""
    if "@" in ref:
        name, version = ref.split("@", 1)
        if not _AGENT_NAME_RE.match(name) or not _AGENT_VERSION_RE.match(version):
            raise ValueError(f"invalid agent ref: {ref!r}")
        return name, version
    if not _AGENT_NAME_RE.match(ref):
        raise ValueError(f"invalid agent name: {ref!r}")
    return ref, None


def format_agent_ref(name: str, version: str | None) -> str:
    """Inverse of `parse_agent_ref`."""
    return f"{name}@{version}" if version else name


_BUDGET_AMOUNT_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]{0,9}):([0-9]+(?:\.[0-9]+)?)$")


def parse_budget_amount(amount: str) -> tuple[str, Decimal]:
    """Parse `currency:decimal`; raise `ValueError` on malformed input."""
    m = _BUDGET_AMOUNT_RE.match(amount)
    if not m:
        raise ValueError(f"invalid budget amount: {amount!r}")
    currency, raw = m.group(1), m.group(2)
    try:
        value = Decimal(raw)
    except InvalidOperation as e:
        raise ValueError(f"invalid budget amount value: {amount!r}") from e
    if value < 0:
        raise ValueError("budget amount must be non-negative")
    return currency, value


def format_budget_amount(currency: str, value: Decimal) -> str:
    return f"{currency}:{value}"


Lease = dict[str, list[str]]
"""A lease maps capability namespace to a list of glob patterns."""


def _ensure_utc_iso8601(value: str) -> datetime:
    """Parse a strict UTC ISO 8601 timestamp (`Z` or `+00:00` only).

    Python 3.11+ `datetime.fromisoformat` accepts a trailing `Z` natively,
    so no `Z` → `+00:00` rewrite is required.
    """
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"invalid ISO 8601 timestamp: {value!r}") from e
    if dt.tzinfo is None or dt.utcoffset() != UTC.utcoffset(dt):
        raise ValueError(f"expires_at must be UTC: {value!r}")
    return dt


class LeaseConstraints(BaseModel):
    """Optional lease constraints (v1.1 §9.5)."""

    model_config = ConfigDict(extra="allow")
    expires_at: str | None = None

    @field_validator("expires_at")
    @classmethod
    def _check_expires_at(cls, v: str | None) -> str | None:
        if v is None:
            return v
        _ensure_utc_iso8601(v)
        return v


class JobSubmitPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    agent: str
    input: Any = None
    lease_request: Lease = Field(default_factory=dict)
    lease_constraints: LeaseConstraints | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)
    max_runtime_sec: int | None = Field(default=None, ge=1, le=86400)
    parent_job_id: str | None = None
    delegate_id: str | None = None

    @field_validator("agent")
    @classmethod
    def _check_agent(cls, v: str) -> str:
        parse_agent_ref(v)
        return v


class CredentialConstraintsPayload(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    cost_budget: tuple[str, ...] = Field(default=(), alias="cost.budget")
    model_use: tuple[str, ...] = Field(default=(), alias="model.use")
    expires_at: str | None = None


class CredentialPayload(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: str
    scheme: Literal["bearer"]
    value: str
    endpoint: str
    profile: str | None = None
    constraints: CredentialConstraintsPayload | None = None


class JobAcceptedPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    job_id: str
    agent: str
    accepted_at: str
    lease: Lease = Field(default_factory=dict)
    lease_constraints: LeaseConstraints | None = None
    budget: dict[str, str] | None = None  # `{currency: "currency:decimal"}` echoed
    parent_job_id: str | None = None
    delegate_id: str | None = None
    trace_id: str | None = None
    credentials: tuple[CredentialPayload, ...] | None = None
    # Optional: echoes the submitting `job.submit` envelope id so a client
    # with concurrent submits can correlate the response to the exact request
    # instead of relying on FIFO arrival order. Older runtimes that omit
    # this field fall back to FIFO matching on the client.
    request_id: str | None = None


class JobCancelPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    reason: str
    code: str | None = None


class JobEventPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: str
    ts: str
    body: dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, v: str) -> str:
        if v in EVENT_KINDS or v.startswith("x-vendor."):
            return v
        raise ValueError(f"unknown event kind: {v!r}")


class JobResultPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    final_status: Literal["success", "cancelled", "timed_out"]
    result: Any | None = None
    result_id: str | None = None
    result_size: int | None = None
    summary: str | None = None
    completed_at: str


class JobErrorPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    final_status: Literal["error"] = "error"
    code: str
    message: str
    retryable: bool = False
    completed_at: str
    details: dict[str, Any] | None = None


class JobSubscribePayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    job_id: str
    history: bool = False
    from_event_seq: int | None = Field(default=None, ge=0)


class JobSubscribedPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    request_id: str
    job_id: str
    current_status: str
    agent: str
    lease: Lease = Field(default_factory=dict)
    parent_job_id: str | None = None
    trace_id: str | None = None
    subscribed_from: int = 0
    replayed: int = 0


class JobUnsubscribePayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    job_id: str


__all__ = (
    "EVENT_KINDS",
    "ArtifactRefBody",
    "CredentialConstraintsPayload",
    "CredentialPayload",
    "DelegateBody",
    "JobAcceptedPayload",
    "JobCancelPayload",
    "JobErrorPayload",
    "JobEventPayload",
    "JobResultPayload",
    "JobSubmitPayload",
    "JobSubscribePayload",
    "JobSubscribedPayload",
    "JobUnsubscribePayload",
    "Lease",
    "LeaseConstraints",
    "LogBody",
    "MetricBody",
    "ProgressBody",
    "ResultChunkBody",
    "StatusBody",
    "ThoughtBody",
    "ToolCallBody",
    "ToolResultBody",
    "format_agent_ref",
    "format_budget_amount",
    "parse_agent_ref",
    "parse_budget_amount",
    "validate_metric_body",
    "validate_progress_body",
    "validate_result_chunk_body",
)
