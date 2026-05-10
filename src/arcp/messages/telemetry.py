"""Observability payloads (RFC §17)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LogLevel = Literal["trace", "debug", "info", "warn", "error", "critical"]


class StandardMetricName(StrEnum):
    """Reserved metric names from §17.3.1."""

    TOKENS_USED = "tokens.used"
    COST_USD = "cost.usd"
    GPU_SECONDS = "gpu.seconds"
    TOOL_INVOCATIONS = "tool.invocations"
    LATENCY_MS = "latency.ms"
    BYTES_IN = "bytes.in"
    BYTES_OUT = "bytes.out"
    ERRORS_TOTAL = "errors.total"


# Reserved metric name -> required unit string per §17.3.1.
RESERVED_METRIC_UNITS: dict[str, str] = {
    StandardMetricName.TOKENS_USED.value: "tokens",
    StandardMetricName.COST_USD.value: "usd",
    StandardMetricName.GPU_SECONDS.value: "seconds",
    StandardMetricName.TOOL_INVOCATIONS.value: "count",
    StandardMetricName.LATENCY_MS.value: "ms",
    StandardMetricName.BYTES_IN.value: "bytes",
    StandardMetricName.BYTES_OUT.value: "bytes",
    StandardMetricName.ERRORS_TOTAL.value: "count",
}


class EventEmitPayload(BaseModel):
    """Generic event emission. ``kind`` lets receivers route by category."""

    model_config = ConfigDict(extra="allow")
    kind: str
    data: dict[str, Any] = Field(default_factory=dict)


class LogPayload(BaseModel):
    """``log`` payload."""

    model_config = ConfigDict(extra="forbid")
    level: LogLevel
    message: str
    attributes: dict[str, Any] | None = None


class MetricPayload(BaseModel):
    """``metric`` payload."""

    model_config = ConfigDict(extra="forbid")
    name: str
    value: float
    unit: str | None = None
    dims: dict[str, str] | None = None


class TraceSpanPayload(BaseModel):
    """Spans are envelope events (carrying OpenTelemetry semantics in payload)."""

    model_config = ConfigDict(extra="forbid")
    name: str
    start: str
    end: str | None = None
    status: Literal["ok", "error", "unset"] = "unset"
    attributes: dict[str, Any] | None = None


PAYLOADS: dict[str, type[BaseModel]] = {
    "event.emit": EventEmitPayload,
    "log": LogPayload,
    "metric": MetricPayload,
    "trace.span": TraceSpanPayload,
}


__all__ = [
    "PAYLOADS",
    "RESERVED_METRIC_UNITS",
    "EventEmitPayload",
    "LogLevel",
    "LogPayload",
    "MetricPayload",
    "StandardMetricName",
    "TraceSpanPayload",
]
