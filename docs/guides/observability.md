# Observability

> Spec reference: ARCP v1.1 §11

The ARCP Python SDK integrates with **OpenTelemetry** for distributed tracing and metrics. Every job, event, and transport frame can emit spans and metrics that flow into your existing observability stack.

## Enabling OpenTelemetry

```python
from arcp.middleware.otel import OtelMiddleware

runtime = ARCPRuntime(
    runtime=RuntimeInfo(name="my-service", version="1.0.0"),
    bearer=StaticBearerVerifier({"tok": "alice"}),
    middleware=[OtelMiddleware()],
)
```

By default, `OtelMiddleware` uses the globally configured OpenTelemetry provider. Set one up before creating the runtime:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
```

## Spans emitted

| Span | Description |
|---|---|
| `arcp.session` | Covers the full session lifetime |
| `arcp.job` | Covers a single job from submit to terminal state |
| `arcp.agent` | Covers the agent function execution |
| `arcp.event` | One span per emitted event (sampled by default) |

## Metrics emitted

| Metric | Type | Description |
|---|---|---|
| `arcp.jobs.active` | Gauge | Currently running jobs |
| `arcp.jobs.total` | Counter | Total jobs submitted |
| `arcp.job.duration_ms` | Histogram | Job wall-clock duration |
| `arcp.job.cost_usd` | Histogram | Job cost (from `ctx.metric({"name": "cost.*", ...})`) |
| `arcp.events.total` | Counter | Total events emitted |

## Propagating trace context

The `OtelMiddleware` automatically propagates W3C trace context over the ARCP transport. Spans created inside an agent function are children of the `arcp.job` span.

```python
async def my_agent(input, ctx):
    tracer = trace.get_tracer("my-agent")
    with tracer.start_as_current_span("fetch-data"):
        data = await fetch(input["url"])
    return {"data": data}
```

## Structured logging

Agent log events (`ctx.log(level, message)`) are emitted as structured log records attached to the `arcp.agent` span:

```python
async def my_agent(input, ctx):
    await ctx.log("info", "processing", extra={"url": input["url"]})
    ...
```

## Custom middleware

Implement the `Middleware` protocol to add custom instrumentation:

```python
class MyMiddleware:
    async def on_job_start(self, ctx) -> None:
        metrics.increment("jobs.started", tags={"agent": ctx.agent})

    async def on_job_end(self, ctx, result) -> None:
        metrics.increment("jobs.completed", tags={"agent": ctx.agent})
```

## Related

- [Host with tracing recipe](../recipes/host-tracing.md)
- [Architecture](../architecture.md)
