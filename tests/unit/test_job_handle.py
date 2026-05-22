"""Unit tests for arcp._client.handles.JobHandle property accessors and streaming."""

from __future__ import annotations

import asyncio
import base64

import pytest

from arcp._client.handles import JobHandle
from arcp._messages.execution import JobAcceptedPayload, JobResultPayload, Lease


def _make_handle(
    *,
    job_id: str = "job_1",
    agent: str = "echo",
    trace_id: str | None = None,
    budget: dict[str, str] | None = None,
) -> JobHandle:
    accepted = JobAcceptedPayload(
        job_id=job_id,
        agent=agent,
        accepted_at="2024-01-01T00:00:00Z",
        lease=Lease(),
        lease_constraints=None,
        budget=budget,
        trace_id=trace_id,
    )
    return JobHandle(job_id=job_id, accepted=accepted)


async def test_agent_ref_property() -> None:
    h = _make_handle(agent="my-agent")
    assert h.agent_ref == "my-agent"


async def test_lease_property() -> None:
    h = _make_handle()
    assert isinstance(h.lease, dict)  # Lease = dict[str, list[str]]


async def test_lease_constraints_property_none() -> None:
    h = _make_handle()
    assert h.lease_constraints is None


async def test_budget_property_none() -> None:
    h = _make_handle(budget=None)
    assert h.budget is None


async def test_budget_property_value() -> None:
    h = _make_handle(budget={"usd": "1.00"})
    assert h.budget == {"usd": "1.00"}


async def test_trace_id_property_none() -> None:
    h = _make_handle(trace_id=None)
    assert h.trace_id is None


async def test_trace_id_property_value() -> None:
    h = _make_handle(trace_id="trace-abc")
    assert h.trace_id == "trace-abc"


async def test_credentials_property_empty() -> None:
    h = _make_handle()
    assert h.credentials == ()


async def test_chunks_iterator_utf8() -> None:
    h = _make_handle()
    h._push_chunk({"data": "hello", "encoding": "utf8"})
    h._push_chunk({"data": " world", "encoding": "utf8"})
    h._chunks.put_nowait(None)  # sentinel

    collected = []
    async for chunk in h.chunks():
        collected.append(chunk)

    assert len(collected) == 2
    assert collected[0]["data"] == "hello"
    assert collected[1]["data"] == " world"


async def test_collect_chunks_utf8() -> None:
    h = _make_handle()
    h._push_chunk({"data": "foo", "encoding": "utf8"})
    h._push_chunk({"data": "bar", "encoding": "utf8"})
    h._chunks.put_nowait(None)

    result = await h.collect_chunks()
    assert result == b"foobar"


async def test_collect_chunks_base64() -> None:
    h = _make_handle()
    raw = b"\x00\x01\x02\x03"
    encoded = base64.b64encode(raw).decode("ascii")
    h._push_chunk({"data": encoded, "encoding": "base64"})
    h._chunks.put_nowait(None)

    result = await h.collect_chunks()
    assert result == raw


async def test_done_awaitable_resolves() -> None:
    h = _make_handle()
    result_payload = JobResultPayload(
        final_status="success",
        result={"x": 1},
        completed_at="2024-01-01T00:00:00Z",
    )
    h._resolve_terminal(result_payload)
    result = await h.done
    assert result.final_status == "success"
    assert result.result == {"x": 1}


async def test_reject_terminal_raises_on_done() -> None:
    h = _make_handle()
    h._reject_terminal(RuntimeError("agent crashed"))
    with pytest.raises(RuntimeError, match="agent crashed"):
        await h.done
