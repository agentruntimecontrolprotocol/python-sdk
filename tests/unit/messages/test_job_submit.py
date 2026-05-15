"""§7.1 — `job.submit` payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from arcp._messages.execution import JobSubmitPayload, LeaseConstraints


def test_minimum_submit() -> None:
    p = JobSubmitPayload(agent="my-agent")
    assert p.lease_request == {}


def test_agent_at_version() -> None:
    p = JobSubmitPayload(agent="my-agent@1.0.0")
    assert p.agent == "my-agent@1.0.0"


def test_invalid_agent_ref() -> None:
    with pytest.raises(ValidationError):
        JobSubmitPayload(agent="@bad")


def test_idempotency_key_length() -> None:
    JobSubmitPayload(agent="a", idempotency_key="x" * 256)
    with pytest.raises(ValidationError):
        JobSubmitPayload(agent="a", idempotency_key="x" * 257)


def test_max_runtime_bounds() -> None:
    JobSubmitPayload(agent="a", max_runtime_sec=86400)
    with pytest.raises(ValidationError):
        JobSubmitPayload(agent="a", max_runtime_sec=0)
    with pytest.raises(ValidationError):
        JobSubmitPayload(agent="a", max_runtime_sec=86401)


def test_lease_constraints_expires_at_must_be_iso_utc() -> None:
    LeaseConstraints(expires_at="2026-05-14T12:00:00Z")
    with pytest.raises(ValidationError):
        LeaseConstraints(expires_at="not-a-date")
