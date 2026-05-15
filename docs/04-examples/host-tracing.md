---
title: "Host: OpenTelemetry"
sdk: python
order: 19
kind: example
---

Wraps the runtime's accept loop with
`arcp.middleware.otel.with_tracing(...)` to propagate W3C trace
context across the wire and emit v1.1 span attributes per spec §11.
The example uses the OTel console exporter so traces are visible
without an external collector.

Source: [`../../examples/host_tracing/`](../../examples/host_tracing/).

```sh
uv run python -m examples.host_tracing.runtime &
uv run python -m examples.host_tracing.client
```

## See also

- Reference: [`../05-reference/middleware-otel.md`](../05-reference/middleware-otel.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §11.
