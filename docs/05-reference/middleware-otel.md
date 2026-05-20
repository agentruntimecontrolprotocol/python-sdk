---
title: "arcp.middleware.otel"
sdk: python
order: 8
kind: reference
---

Module `arcp.middleware.otel`. Wraps a `Transport` with W3C trace
context propagation and emits the v1.1 span attributes from spec
§11 (`arcp.session.id`, `arcp.job.id`, `arcp.envelope.type`, etc.).

## Symbols

| Name           | Kind     | Summary                                                            |
| -------------- | -------- | ------------------------------------------------------------------ |
| `with_tracing` | function | Returns a `Transport` decorator that records spans for send / recv. |

## with_tracing

```python
def with_tracing(
    inner: Transport,
    *,
    tracer: opentelemetry.trace.Tracer | None = None,
) -> Transport: ...
```

Use either side of the wire. On the client:

```python
from arcp import WebSocketTransport
from arcp.middleware.otel import with_tracing

raw = await WebSocketTransport.connect(url)
transport = with_tracing(raw)
await client.connect(transport)
```

On the runtime, pass a wrapped transport into `runtime.accept`. The
decorator injects `traceparent` / `tracestate` headers into outbound
envelopes and reads them from inbound envelopes to continue the
upstream trace.

**Raises**: never; exceptions inside the inner transport propagate
unchanged.

## See also

- Example: [`../04-examples/host-tracing.md`](../04-examples/host-tracing.md).
- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §11.
