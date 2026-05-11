"""OTLP exporter for `metric` and `trace.span` envelopes (RFC §17)."""

from __future__ import annotations

from arcp import Envelope


class OTLPSink:
    def __init__(self, *, endpoint: str) -> None:
        self._endpoint = endpoint
        # Real version: opentelemetry-exporter-otlp + meter/tracer
        # providers wired here. The mapping below is the only
        # ARCP-aware part.

    async def handle(self, env: Envelope) -> None:
        match env.type:
            case "metric":
                # Standard names (§17.3.1): tokens.used, cost.usd,
                # latency.ms, ... map directly to OTLP counters /
                # histograms.
                ...
            case "trace.span":
                # `trace.span` mirrors OpenTelemetry's span shape.
                ...
