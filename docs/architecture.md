# Architecture

This document explains how the ARCP Python SDK is structured, what each layer does, and how the pieces fit together at runtime.

## Package layout

```
arcp/
├── __init__.py          # Public surface: ARCPClient, ARCPRuntime, types
├── client/              # ARCPClient, JobHandle, JobSubscription
├── runtime/             # ARCPRuntime, verifiers, agent registry
├── _transport/          # Transport protocol + concrete implementations
├── _envelope.py         # Wire format (de)serialisation
├── _errors.py           # 15 typed exceptions (§12)
├── _version.py
├── _extensions.py       # Vendor extension helpers (§15)
└── middleware/
    ├── asgi.py          # ASGI adapter (FastAPI, Starlette, ...)
    ├── aiohttp.py       # aiohttp adapter
    └── otel.py          # OpenTelemetry span / metric export
```

## The six-piece protocol

ARCP defines six protocol concepts that form concentric rings:

```
┌─────────────────────────────────────────┐
│  Session  (§6)                          │
│  ┌───────────────────────────────────┐  │
│  │  Job  (§7)                        │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │  Events  (§8)               │  │  │
│  │  └─────────────────────────────┘  │  │
│  │  ┌────────────┐ ┌──────────────┐  │  │
│  │  │ Lease (§9) │ │Delegation(§10│  │  │
│  │  └────────────┘ └──────────────┘  │  │
│  └───────────────────────────────────┘  │
│  Observability  (§11)                   │
└─────────────────────────────────────────┘
```

### Sessions (§6)

A session is the authenticated connection between a client and a runtime. The client presents a bearer token; the runtime verifies it and assigns a *principal* (a string identity like an email address).

```python
from arcp.runtime import ARCPRuntime, StaticBearerVerifier

runtime = ARCPRuntime(
    runtime=RuntimeInfo(name="my-service", version="1.0.0"),
    bearer=StaticBearerVerifier({"secret-token": "alice@example.com"}),
)
```

See [Sessions guide](guides/sessions.md) and [Auth guide](guides/auth.md).

### Envelopes

Every message on the wire is an **envelope**: a JSON object with a `type` discriminator and a `payload`. The SDK handles (de)serialisation transparently via `arcp._envelope`. You never construct envelopes directly.

### Jobs (§7)

A job is a unit of work: an agent name, an input payload, optional lease constraints, and an optional idempotency key.

```python
handle = await client.submit(
    agent="summarise",
    input={"url": "https://example.com"},
    lease_request={"max_cost_usd": 0.10, "expires_in_s": 60},
    idempotency_key="req-abc123",
)
```

See [Jobs guide](guides/jobs.md).

### Events (§8)

While a job runs, the runtime emits a stream of typed events:

| Event kind | Meaning |
|---|---|
| `job.queued` | Job accepted and placed in queue |
| `job.started` | Agent function invoked |
| `job.log` | Log line from `ctx.log(level, message)` |
| `job.progress` | Progress update from `ctx.progress(done, total)` |
| `job.result_chunk` | Streaming result fragment |
| `job.completed` | Agent returned; payload contains final result |
| `job.failed` | Agent raised an exception |
| `job.cancelled` | Job was cancelled before completion |
| `job.heartbeat` | Keep-alive ping |

See [Job events guide](guides/job-events.md).

### Leases (§9)

A lease is a spending cap attached to a job. Clients request a lease at submit time; the runtime enforces it.

```python
handle = await client.submit(
    agent="gpt-4-summary",
    input={"text": long_text},
    lease_request={"max_cost_usd": 0.05},
)
```

See [Leases guide](guides/leases.md).

### Delegation (§10)

An agent can act as a client to another runtime. The originating client's identity flows through the chain via signed delegation tokens.

See [Delegation guide](guides/delegation.md).

### Observability (§11)

The SDK emits OpenTelemetry spans and metrics via `arcp.middleware.otel`.

See [Observability guide](guides/observability.md).

## Runtime and client lifecycle

```
client_transport, server_transport = pair_memory_transports()

                Client side                      Runtime side
  ─────────────────────────────────   ─────────────────────────────────
  ARCPClient.connect(client_transport) ──►  ARCPRuntime.accept(server_transport)
       │                                          │
  negotiate capabilities                    verify bearer token
       │                                          │
  submit(agent, input)  ──────────────►   route to registered agent fn
       │                                          │
  JobHandle  ◄──── event stream ────────── agent executes
       │                                          │
  await handle.done  ◄──── job.completed ─── agent returns
```

## Agent versions (§6.2)

Clients can pin to a specific agent version:

```python
handle = await client.submit(
    agent="summarise@2",
    input={"url": "https://example.com"},
)
```

Runtimes register versioned agents:

```python
runtime.register_agent_version("summarise", "1", summarise_v1)
runtime.register_agent_version("summarise", "2", summarise_v2)
```

If the client omits the version suffix, the runtime uses the latest registered version.

## Middleware

### ASGI (FastAPI, Starlette)

```python
from arcp.middleware.asgi import ARCPMiddleware

app = FastAPI()
app.add_middleware(ARCPMiddleware, runtime=runtime)
```

### aiohttp

```python
from arcp.middleware.aiohttp import attach_arcp

app = web.Application()
attach_arcp(app, runtime=runtime)
```

### OpenTelemetry

```python
from arcp.middleware.otel import OtelMiddleware

runtime = ARCPRuntime(..., middleware=[OtelMiddleware()])
```

See [Observability guide](guides/observability.md) for full configuration.

## Error hierarchy

All SDK exceptions inherit from `ARCPError`. The 15 typed exceptions map directly to spec §12 error codes.

See [Errors guide](guides/errors.md) and [Troubleshooting](troubleshooting.md).
