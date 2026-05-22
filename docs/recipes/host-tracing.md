# Host: OpenTelemetry

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

- Guide: [Observability](../guides/observability.md).
- Spec: [ARCP v1.1 §11](https://arcp.dev/spec/v1.1#section-11).
