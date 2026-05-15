"""OpenTelemetry transport wrapper: propagates W3C traceparent + emits spans per envelope."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.trace import SpanKind, Tracer

from .._extensions import OTEL_EXTENSION_KEY
from .._transport.base import Transport, TransportClosed

_ENV_ATTR_KEYS: tuple[tuple[str, str], ...] = (
    ("session_id", "arcp.session_id"),
    ("job_id", "arcp.job_id"),
    ("trace_id", "arcp.trace_id"),
    ("event_seq", "arcp.event_seq"),
)


def _payload_attrs(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    agent = payload.get("agent")
    if isinstance(agent, str):
        out["arcp.agent"] = agent
    lease = payload.get("lease") or payload.get("lease_request")
    if isinstance(lease, dict):
        out["arcp.lease.capabilities"] = ",".join(sorted(lease.keys()))
    constraints = payload.get("lease_constraints")
    if isinstance(constraints, dict) and constraints.get("expires_at"):
        out["arcp.lease.expires_at"] = constraints["expires_at"]
    budget = payload.get("budget")
    if isinstance(budget, dict):
        out["arcp.budget.remaining"] = json.dumps(budget, sort_keys=True)
    return out


def _extract_attrs(env: dict[str, Any], direction: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "arcp.direction": direction,
        "arcp.type": env.get("type"),
        "arcp.id": env.get("id"),
    }
    for env_key, span_key in _ENV_ATTR_KEYS:
        if env_key in env:
            out[span_key] = env[env_key]
    out.update(_payload_attrs(env.get("payload", {}) or {}))
    return out


class _TracedTransport:
    def __init__(
        self,
        inner: Transport,
        tracer: Tracer,
        send_span_name: Callable[[dict[str, Any]], str] | None,
        recv_span_name: Callable[[dict[str, Any]], str] | None,
    ) -> None:
        self._inner = inner
        self._tracer = tracer
        self._send_name = send_span_name or (lambda env: f"arcp.send {env.get('type', '?')}")
        self._recv_name = recv_span_name or (lambda env: f"arcp.recv {env.get('type', '?')}")

    async def send(self, envelope: dict[str, Any]) -> None:
        with self._tracer.start_as_current_span(
            self._send_name(envelope), kind=SpanKind.PRODUCER
        ) as span:
            for k, v in _extract_attrs(envelope, "out").items():
                if v is not None:
                    span.set_attribute(k, v)
            extensions = dict(envelope.get("extensions") or {})
            carrier: dict[str, str] = {}
            propagate.inject(carrier)
            if carrier:
                extensions[OTEL_EXTENSION_KEY] = carrier
                envelope = {**envelope, "extensions": extensions}
            await self._inner.send(envelope)

    async def recv(self) -> dict[str, Any]:
        envelope = await self._inner.recv()
        extensions = envelope.get("extensions") or {}
        carrier = extensions.get(OTEL_EXTENSION_KEY) if isinstance(extensions, dict) else None
        ctx = propagate.extract(carrier) if isinstance(carrier, dict) else None
        with self._tracer.start_as_current_span(
            self._recv_name(envelope), context=ctx, kind=SpanKind.CONSUMER
        ) as span:
            for k, v in _extract_attrs(envelope, "in").items():
                if v is not None:
                    span.set_attribute(k, v)
        return envelope

    async def close(self) -> None:
        await self._inner.close()

    @property
    def is_closed(self) -> bool:
        return self._inner.is_closed


def with_tracing(
    inner: Transport,
    *,
    tracer: Tracer | None = None,
    send_span_name: Callable[[dict[str, Any]], str] | None = None,
    recv_span_name: Callable[[dict[str, Any]], str] | None = None,
) -> Transport:
    """Wrap `inner` so each send/recv produces an OTel span and propagates traceparent."""
    t = tracer or trace.get_tracer("arcp.middleware.otel")
    return _TracedTransport(inner, t, send_span_name, recv_span_name)


# silence unused TransportClosed
_ = TransportClosed


__all__ = ("OTEL_EXTENSION_KEY", "with_tracing")
