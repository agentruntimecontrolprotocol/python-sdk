# ARCP — Agent Runtime Control Protocol (Python reference)

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python ≥ 3.11](https://img.shields.io/badge/python-%E2%89%A53.11-blue)](pyproject.toml)
[![ARCP v1.1](https://img.shields.io/badge/arcp-v1.1-blue)](https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md)

Reference implementation of ARCP v1.1 for Python. The wire is defined
in [the ARCP spec](https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md);
this SDK is one of eleven implementations tracked in the workspace's
per-SDK conformance pages.

## Install

```sh
uv add arcp
```

```sh
pip install arcp
```

The Python SDK ships as a single distribution. Subpackages:

| Subpackage                  | What it contains                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------- |
| `arcp`                      | Top-level re-exports (`ARCPClient`, `ARCPRuntime`, `MemoryTransport`, `pair_memory_transports`, errors, version constants). |
| `arcp.client`               | `ARCPClient`, `JobHandle`, `JobSubscription`, `AutoAckOptions`.                             |
| `arcp.runtime`              | `ARCPRuntime`, `JobContext`, `SessionContext`, agent registry, lease helpers.               |
| `arcp.transport`            | `Transport` protocol, `MemoryTransport`, `WebSocketTransport`, `StdioTransport`.            |
| `arcp.middleware.asgi`      | `arcp_asgi_app(runtime, *, allowed_hosts)` for Starlette / FastAPI / Litestar / Quart.      |
| `arcp.middleware.aiohttp`   | `arcp_aiohttp_handler(runtime)` and `serve_arcp_aiohttp(...)` for `aiohttp.web.Application`. |
| `arcp.middleware.otel`      | `with_tracing(inner, *, tracer)` — W3C trace context + v1.1 span attrs (§11).               |

All of the above ship in one wheel; no à-la-carte install.

## Quickstart

```python
import asyncio

from arcp import (
    ARCPClient, ClientInfo, RuntimeInfo, pair_memory_transports,
)
from arcp.runtime import ARCPRuntime, StaticBearerVerifier

TOKEN = "demo"


async def echo(input_value, ctx):
    await ctx.log("info", "echo started")
    return {"echoed": input_value}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="quickstart", version="1.1.0"),
        bearer=StaticBearerVerifier({TOKEN: "me@example.com"}),
    )
    runtime.register_agent("echo", echo)

    client_t, server_t = pair_memory_transports()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(runtime.accept(server_t))

        client = ARCPClient(
            client=ClientInfo(name="quickstart-client", version="1.0.0"),
            token=TOKEN,
        )
        await client.connect(client_t)
        handle = await client.submit(agent="echo", input={"hi": 1})
        result = await handle.done
        print(result.result)
        await client.close()


asyncio.run(main())
```

The runnable two-process WebSocket variant is at
[`examples/submit_and_stream/`](examples/submit_and_stream/).

## Core concepts

| Piece     | Spec | Module                   |
| --------- | ---- | ------------------------ |
| Envelope  | §5   | `arcp.Envelope`          |
| Transport | §4   | `arcp.transport`         |
| Session   | §6   | `arcp.runtime.SessionContext`, `arcp.client.ARCPClient` |
| Job       | §7   | `arcp.runtime.Job`, `arcp.client.JobHandle` |
| Event     | §8   | `arcp.runtime.JobContext` (emitters) |
| Lease     | §9   | `arcp.runtime.validate_lease_op`, `LeaseConstraints` |
| Delegation| §10  | `JobContext.delegate(...)` (recursive submit) |

Cancellation: `client.cancel_job(job_id)` propagates as
`asyncio.CancelledError` into the agent body; cleanup runs before the
terminal `job.error` (`code: "CANCELLED"`) ships. Event payloads are
discriminated unions on `payload.kind`, validated with pydantic v2.

## v1.1 additions

The nine v1.1 features negotiate per spec §6.2 (intersection of the
client's `capabilities.features` with the runtime's, in client
order): [`heartbeat`](docs/03-features/heartbeats.md),
[`ack`](docs/03-features/event-ack.md),
[`list_jobs`](docs/03-features/list-jobs.md),
[`subscribe`](docs/03-features/subscribe.md),
[`agent_versions`](docs/03-features/agent-versions.md),
[`lease_expires_at`](docs/03-features/lease-expires-at.md),
[`cost.budget`](docs/03-features/cost-budget.md),
[`progress`](docs/03-features/progress.md),
[`result_chunk`](docs/03-features/result-chunk.md). Features absent
from the negotiated set behave as if unsupported on both sides; see
[`docs/03-features/capability-negotiation.md`](docs/03-features/capability-negotiation.md).

## Running the runtime

### Programmatic

```python
import asyncio

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, StaticBearerVerifier

runtime = ARCPRuntime(
    runtime=RuntimeInfo(name="my-runtime", version="1.1.0"),
    bearer=StaticBearerVerifier({"tok": "me@example.com"}),
)
runtime.register_agent("echo", lambda inp, ctx: {"echoed": inp})


async def main() -> None:
    server = await serve_websocket(
        runtime.accept, host="127.0.0.1", port=7777, path="/arcp",
    )
    async with server:
        await server.serve_forever()


asyncio.run(main())
```

To mount inside an existing ASGI app, use
`arcp.middleware.asgi.arcp_asgi_app(runtime, allowed_hosts=[...])`
on a WebSocket route.

### CLI

```sh
uv run arcp serve   --host 127.0.0.1 --port 7777 \
                    --token tok --principal me@example.com
uv run arcp submit  --url ws://127.0.0.1:7777/arcp \
                    --token tok --agent echo --input '{"hi":1}'
uv run arcp tail    --url ws://127.0.0.1:7777/arcp \
                    --token tok --job-id job_01J...
uv run arcp replay  --db arcp.db --session sess_XYZ --after-seq 0
```

Commands are implemented in [`src/arcp/cli.py`](src/arcp/cli.py).

## Writing clients

```python
import os
import asyncio

from arcp import ARCPClient, ClientInfo, WebSocketTransport


async def main() -> None:
    transport = await WebSocketTransport.connect("wss://runtime.example.com/arcp")
    client = ARCPClient(
        client=ClientInfo(name="my-client", version="1.0.0"),
        token=os.environ["TOKEN"],
    )
    await client.connect(transport)
    try:
        handle = await client.submit(
            agent="weekly-report",
            input={"week": "2026-W19"},
            lease_request={"net.fetch": ["s3://example/**"]},
            idempotency_key="weekly-report-2026-W19",
        )
        async for event in handle.events():
            # elided: render event to stdout / UI
            pass
        result = await handle.done
        print(result.result)
    finally:
        await client.close()


asyncio.run(main())
```

`client.connect(transport)` performs the handshake and starts the
read pump; `client.close()` sends `session.bye` (spec §6.7) and
closes the transport. Cancellation propagates `asyncio.CancelledError`
into `handle.done`.

## Conformance

Per-section status, with source citations, lives at
[`docs/06-conformance.md`](docs/06-conformance.md). All v1.1
normative requirements are implemented; the deferred items listed at
the bottom of that page are intentional, not bugs.

## Examples

Core (v1.0):

| Example                                   | What it shows                          |
| ----------------------------------------- | -------------------------------------- |
| [`submit-and-stream`](docs/04-examples/submit-and-stream.md) | Connect, submit, iterate events, close. |
| [`delegate`](docs/04-examples/delegate.md)               | Parent agent submits a child job.      |
| [`resume`](docs/04-examples/resume.md)                   | Reattach to a session and replay.      |
| [`idempotent-retry`](docs/04-examples/idempotent-retry.md) | Same key → same `job_id`.            |
| [`lease-violation`](docs/04-examples/lease-violation.md) | Authorize outside the granted lease.   |
| [`cancel`](docs/04-examples/cancel.md)                   | `job.cancel` → terminal `CANCELLED`.   |
| [`stdio`](docs/04-examples/stdio.md)                     | Child-process subagent over pipes.     |
| [`vendor-extensions`](docs/04-examples/vendor-extensions.md) | `x-vendor.*` passthrough.            |
| [`custom-auth`](docs/04-examples/custom-auth.md)         | Custom `BearerVerifier`.               |

v1.1 features:

| Example                                     | Feature           |
| ------------------------------------------- | ----------------- |
| [`heartbeat`](docs/04-examples/heartbeat.md)             | `heartbeat`        |
| [`ack-backpressure`](docs/04-examples/ack-backpressure.md) | `ack`            |
| [`list-jobs`](docs/04-examples/list-jobs.md)             | `list_jobs`        |
| [`subscribe`](docs/04-examples/subscribe.md)             | `subscribe`        |
| [`agent-versions`](docs/04-examples/agent-versions.md)   | `agent_versions`   |
| [`lease-expires-at`](docs/04-examples/lease-expires-at.md) | `lease_expires_at` |
| [`cost-budget`](docs/04-examples/cost-budget.md)         | `cost.budget`      |
| [`progress`](docs/04-examples/progress.md)               | `progress`         |
| [`result-chunk`](docs/04-examples/result-chunk.md)       | `result_chunk`     |

Host integrations:

| Example                                         | Host         |
| ----------------------------------------------- | ------------ |
| [`host-tracing`](docs/04-examples/host-tracing.md) | OpenTelemetry |
| [`host-asgi`](docs/04-examples/host-asgi.md)       | Starlette / FastAPI |
| [`host-aiohttp`](docs/04-examples/host-aiohttp.md) | aiohttp      |

## Development

```sh
uv sync                # install incl. dev extras
uv run pytest          # tests/
uv run ruff check      # lint + format check
uv run pyright         # strict type check
```

## License

[Apache-2.0](LICENSE).
