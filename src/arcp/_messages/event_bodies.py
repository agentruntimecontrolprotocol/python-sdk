"""TypedDict event-kind bodies and inbound body validators (spec §8.2 + §8.4)."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class LogBody(TypedDict, total=False):
    level: str
    message: str
    attributes: dict[str, Any]


class ThoughtBody(TypedDict, total=False):
    text: str


class ToolCallBody(TypedDict, total=False):
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


class ToolResultBody(TypedDict, total=False):
    tool_call_id: str
    output: Any
    error: dict[str, Any]


class StatusBody(TypedDict, total=False):
    phase: str
    message: str


class MetricBody(TypedDict, total=False):
    name: str
    value: float
    unit: str
    attributes: dict[str, Any]


class ArtifactRefBody(TypedDict, total=False):
    artifact_id: str
    media_type: str
    size_bytes: int
    uri: str
    summary: str


class DelegateBody(TypedDict, total=False):
    child_job_id: str
    agent: str


class ProgressBody(TypedDict, total=False):
    current: int
    total: int
    units: str
    message: str


class ResultChunkBody(TypedDict, total=False):
    result_id: str
    chunk_seq: int
    data: str
    encoding: Literal["utf8", "base64"]
    more: bool


EVENT_KINDS: tuple[str, ...] = (
    "log",
    "thought",
    "tool_call",
    "tool_result",
    "status",
    "metric",
    "artifact_ref",
    "delegate",
    "progress",
    "result_chunk",
)


def validate_progress_body(body: dict[str, Any]) -> None:
    """Enforce `current >= 0` and `current <= total` when `total` is present."""
    cur = body.get("current")
    if not isinstance(cur, int) or cur < 0:
        raise ValueError("progress.current must be a non-negative integer")
    total = body.get("total")
    if total is not None:
        if not isinstance(total, int) or total < 0:
            raise ValueError("progress.total must be a non-negative integer")
        if cur > total:
            raise ValueError("progress.current must be <= progress.total")


def validate_result_chunk_body(body: dict[str, Any]) -> None:
    """Enforce shape rules on a `result_chunk` event body (§8.4)."""
    if "result_id" not in body or not isinstance(body["result_id"], str):
        raise ValueError("result_chunk.result_id is required and must be string")
    if "chunk_seq" not in body or not isinstance(body["chunk_seq"], int) or body["chunk_seq"] < 0:
        raise ValueError("result_chunk.chunk_seq must be a non-negative integer")
    if "data" not in body or not isinstance(body["data"], str):
        raise ValueError("result_chunk.data is required and must be string")
    encoding = body.get("encoding", "utf8")
    if encoding not in ("utf8", "base64"):
        raise ValueError("result_chunk.encoding must be one of utf8|base64")
    if "more" not in body or not isinstance(body["more"], bool):
        raise ValueError("result_chunk.more is required and must be bool")


def validate_metric_body(body: dict[str, Any]) -> None:
    """`name`/`value` required; cost.* metrics negative `value` rejected."""
    name = body.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("metric.name is required and must be a non-empty string")
    value = body.get("value")
    if not isinstance(value, (int, float)):
        raise ValueError("metric.value is required and must be numeric")
    if name.startswith("cost.") and value < 0:
        raise ValueError("cost.* metrics must have non-negative value")


__all__ = (
    "EVENT_KINDS",
    "ArtifactRefBody",
    "DelegateBody",
    "LogBody",
    "MetricBody",
    "ProgressBody",
    "ResultChunkBody",
    "StatusBody",
    "ThoughtBody",
    "ToolCallBody",
    "ToolResultBody",
    "validate_metric_body",
    "validate_progress_body",
    "validate_result_chunk_body",
)
