# host_tracing

OpenTelemetry `ConsoleSpanExporter` on both client and server, with the
W3C `traceparent` riding the envelope's
`extensions["x-vendor.opentelemetry.tracecontext"]` slot (spec §11).

```
python examples/host_tracing/server.py     # terminal 1
python examples/host_tracing/client.py     # terminal 2
```

Client success: at least one client span and one server span share the
same `trace_id`. Spans print to stdout on both sides — this is the only
example with stdout noise from instrumentation.
