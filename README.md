<h3 align="center">ARCP Python SDK</h3>

<p align="center"><strong>Python SDK for the Agent Runtime Control Protocol (ARCP) — submit, observe, and control long-running agent jobs from Python.</strong></p>

<p align="center">
  <a href="https://pypi.org/project/arcp/"><img alt="PyPI" src="https://img.shields.io/pypi/v/arcp.svg"></a>
  <a href="https://pypi.org/project/arcp/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/arcp.svg"></a>
  <a href="https://github.com/agentruntimecontrolprotocol/python-sdk/actions/workflows/test.yml"><img alt="CI" src="https://github.com/agentruntimecontrolprotocol/python-sdk/actions/workflows/test.yml/badge.svg"></a>
  <a href="https://codecov.io/gh/agentruntimecontrolprotocol/python-sdk"><img alt="codecov" src="https://codecov.io/gh/agentruntimecontrolprotocol/python-sdk/graph/badge.svg"></a>
  <a href="https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md"><img alt="ARCP" src="https://img.shields.io/badge/ARCP-v1.1%20draft-blue"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-lightgrey"></a>
</p>

<p align="center">
  <a href="https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md">Specification</a> ·
  <a href="#concepts">Concepts</a> ·
  <a href="#installation">Install</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="docs/">Guides</a> ·
  <a href="docs/">API reference</a>
</p>

---

`arcp` is the Python reference implementation of [ARCP](https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md), the Agent Runtime Control Protocol. It covers both sides of the wire — `arcp.client.ARCPClient` for submitting and observing jobs, `arcp.runtime.ARCPRuntime` for hosting agents — so either side can talk to any conformant peer in any language without hand-rolling the envelope, sequencing, or lease enforcement.

ARCP itself is a transport-agnostic wire protocol for long-running AI agent jobs. It owns the parts of agent infrastructure that don't change between products — sessions, durable event streams, capability leases, budgets, resume — and stays out of the parts that do. ARCP wraps the agent function; it does not define how agents are built, how tools are exposed (that's MCP), or how telemetry is exported (that's OpenTelemetry).

## Installation

Requires Python 3.11 or later. The SDK ships as a single wheel containing the client, runtime, transports, ASGI/aiohttp middleware, the OpenTelemetry middleware, and the `arcp` CLI. Install from PyPI with `pip`, `uv`, or any PEP 517 resolver; the optional `jwks` extra pulls in `httpx` for remote JWKS verification.

```sh
pip install arcp
# or, with uv:
uv add arcp
# with the JWKS extra:
pip install "arcp[jwks]"
```

## Quick start

Connect to a runtime, submit a job, stream its events to completion:

```python
import asyncio
import contextlib
import os

from arcp import ClientInfo, WebSocketTransport
from arcp.client import ARCPClient


async def main() -> None:
    client = ARCPClient(
        client=ClientInfo(name="quickstart", version="1.0.0"),
        token=os.environ["ARCP_TOKEN"],
    )
    async with contextlib.aclosing(client):
        transport = await WebSocketTransport.connect("wss://runtime.example.com/arcp")
        await client.connect(transport)

        handle = await client.submit(
            agent="data-analyzer",
            input={"dataset": "s3://example/sales.csv"},
            lease_request={"net.fetch": ["s3://example/**"]},
        )
        async for event in handle.events():
            print(f"[{event['kind']}]", event["body"])

        result = await handle.done
        print("final:", result.final_status, result.result)


asyncio.run(main())
```

This is the whole shape of the SDK: open a session, submit work, consume an ordered event stream, get a terminal result or error. Everything below is detail on those four moves.

## Concepts

ARCP organizes everything around four concerns — **identity**, **durability**, **authority**, and **observability** — expressed through five core objects:

- **Session** — a connection between a client and a runtime. A session carries identity (a bearer token), negotiates a feature set in a `hello`/`welcome` handshake, and is *resumable*: if the transport drops, you reconnect with a resume token and the runtime replays buffered events. Jobs outlive the session that started them. See [§6](https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md).
- **Job** — one unit of agent work submitted into a session. A job has an identity, an optional idempotency key, a resolved agent version, and a lifecycle that ends in exactly one terminal state: `success`, `error`, `cancelled`, or `timed_out`. See [§7](https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md).
- **Event** — the ordered, session-scoped stream a job emits: logs, thoughts, tool calls and results, status, metrics, artifact references, progress, and streamed result chunks. Events carry strictly monotonic sequence numbers so the stream survives reconnects gap-free. See [§8](https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md).
- **Lease** — the authority a job runs under, expressed as capability grants (`fs.read`, `fs.write`, `net.fetch`, `tool.call`, `agent.delegate`, `cost.budget`, `model.use`). The runtime enforces the lease at every operation boundary; a job can never act outside it. Leases may carry a budget and an expiry, and may be subset and handed to sub-agents via delegation. See [§9](https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md).
- **Subscription** — read-only attachment to a job started elsewhere (e.g. a dashboard watching a job a CLI submitted). A subscriber observes the live event stream but cannot cancel or mutate the job. Distinct from *resume*, which continues the original session and carries cancel authority. See [§7.6](https://github.com/agentruntimecontrolprotocol/spec/blob/main/docs/draft-arcp-1.1.md).

The SDK models each of these as first-class objects; the rest of this README shows how.

## Guides

### Sessions and resume

Open a session, negotiate features, and reconnect transparently after a transport drop using the resume token — jobs keep running server-side while you're gone.

```python
import asyncio
import contextlib
import os

from arcp import ClientInfo, SessionResume, WebSocketTransport
from arcp.client import ARCPClient

URL = "wss://runtime.example.com/arcp"
TOKEN = os.environ["ARCP_TOKEN"]


def new_client() -> ARCPClient:
    return ARCPClient(
        client=ClientInfo(name="resumable", version="1.0.0"),
        token=TOKEN,
    )


async def main() -> None:
    first = new_client()
    transport1 = await WebSocketTransport.connect(URL)
    welcome = await first.connect(transport1)
    session_id = welcome.session_id
    resume_token = welcome.resume_token

    handle = await first.submit(agent="long-running", input={})
    async for _ in handle.events():
        if first.latest_event_seq >= 2:
            break
    last_seq = first.latest_event_seq

    # Drop the transport without sending session.bye; the job keeps running.
    await transport1.close()

    second = new_client()
    async with contextlib.aclosing(second):
        transport2 = await WebSocketTransport.connect(URL)
        await second.resume(
            transport2,
            resume=SessionResume(
                session_id=session_id,
                resume_token=resume_token,
                last_event_seq=last_seq,
            ),
        )
        # The runtime replays every event with seq > last_seq, then resumes live streaming.


asyncio.run(main())
```

### Submitting jobs

Submit a job with an agent (optionally version-pinned as `name@version`), an input, and an optional lease request, idempotency key, and runtime limit.

```python
from datetime import UTC, datetime, timedelta

from arcp import LeaseConstraints

expires_at = (datetime.now(UTC) + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")

handle = await client.submit(
    agent="weekly-report@2.1.0",
    input={"week": "2026-W19"},
    lease_request={"net.fetch": ["s3://reports/**"]},
    lease_constraints=LeaseConstraints(expires_at=expires_at),
    idempotency_key="weekly-report-2026-W19",
    max_runtime_sec=300,
)

print("job_id =", handle.job_id)
print("effective lease =", handle.lease)
print("resolved agent =", handle.agent_ref)
```

### Consuming events

Iterate the ordered event stream — `log`, `thought`, `tool_call`, `tool_result`, `status`, `metric`, `artifact_ref`, `progress`, `result_chunk` — and optionally acknowledge progress so the runtime can release buffered events early.

```python
from arcp import ClientInfo
from arcp.client import ARCPClient, AutoAckOptions

client = ARCPClient(
    client=ClientInfo(name="ack-demo", version="1.0.0"),
    token=TOKEN,
    # Coalesced session.ack: send when 32+ events have accrued, at most every 250 ms.
    auto_ack=AutoAckOptions(every_n=32, interval_sec=0.25),
)

handle = await client.submit(agent="chatty", input={})

async for event in handle.events():
    kind = event["kind"]
    body = event["body"]
    if kind == "log":
        print(body.get("message"))
    elif kind == "tool_call":
        print("->", body.get("name"), body.get("arguments"))
    elif kind == "metric":
        print("metric", body)
    elif kind == "progress":
        print("progress", body)
    # Or ack manually: await client.ack(client.latest_event_seq)
```

### Leases and budgets

Request capabilities, a budget, and an expiry; read budget-remaining metrics as they arrive; handle the runtime's enforcement decisions.

```python
from datetime import UTC, datetime, timedelta

from arcp import BudgetExhaustedError, LeaseConstraints, LeaseExpiredError

expires_at = (datetime.now(UTC) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")

handle = await client.submit(
    agent="web-research",
    input={"iterations": 8, "per_call_usd": 0.3},
    lease_request={
        "tool.call": ["search.*", "fetch.*"],
        "cost.budget": ["USD:1.00"],
    },
    lease_constraints=LeaseConstraints(expires_at=expires_at),
)

print("initial budget =", handle.budget)

try:
    async for event in handle.events():
        if event["kind"] == "metric" and event["body"].get("name") == "cost.budget.remaining":
            body = event["body"]
            print(f"budget remaining: {body['value']:.2f} {body.get('unit', '')}")
    await handle.done
except (BudgetExhaustedError, LeaseExpiredError) as err:
    # Never retryable: resubmit with a fresh lease or budget instead.
    print("job ended:", err.code, err.message)
```

### Subscribing to jobs

Attach read-only to a job submitted elsewhere and observe its live stream (with optional history replay) without cancel authority.

```python
from arcp import ClientInfo, ListJobsFilter, WebSocketTransport
from arcp.client import ARCPClient

observer = ARCPClient(
    client=ClientInfo(name="dashboard", version="1.0.0"),
    token=TOKEN,
    features=("list_jobs", "subscribe"),
)
await observer.connect(await WebSocketTransport.connect(URL))

listing = await observer.list_jobs(filter=ListJobsFilter(status=("running",)))
sub = await observer.subscribe(listing.jobs[0].job_id, history=True)
print(f"subscribed from seq={sub.subscribed_from} replayed={sub.replayed}")

async for event in sub.handle.events():
    print(f"[seq>{sub.subscribed_from}] {event['kind']}")

# ... later ...
await observer.unsubscribe(sub.job_id)
```

### Error handling

Catch the typed error taxonomy and respect the `retryable` flag — `LEASE_EXPIRED` and `BUDGET_EXHAUSTED` are never retryable; a naive retry fails identically.

```python
from arcp import ARCPError, BudgetExhaustedError, LeaseExpiredError

try:
    handle = await client.submit(agent="flaky", input={})
    await handle.done
except (LeaseExpiredError, BudgetExhaustedError):
    # Resubmit with a fresh lease / budget instead of retrying.
    raise
except ARCPError as err:
    if err.retryable:
        # Safe to retry with backoff (e.g. INTERNAL_ERROR, TIMEOUT).
        ...
    else:
        raise
```

## Feature support

ARCP features this SDK negotiates during the `hello`/`welcome` handshake:

| Feature flag | Status |
|---|---|
| `heartbeat` | Supported |
| `ack` | Supported |
| `list_jobs` | Supported |
| `subscribe` | Supported |
| `lease_expires_at` | Supported |
| `cost.budget` | Supported |
| `model.use` | Supported |
| `provisioned_credentials` | Supported |
| `progress` | Supported |
| `result_chunk` | Supported |
| `agent_versions` | Supported |

## Transport

ARCP is transport-agnostic. This SDK ships a WebSocket transport (default), an stdio transport for in-process child runtimes, and an in-memory transport for tests. WebSocket is the default for networked runtimes; stdio is used for in-process child runtimes. Select one by constructing the corresponding object (`WebSocketTransport.connect(url)`, `StdioTransport(...)`, `pair_memory_transports()`) and passing it to `client.connect(transport)`; the `arcp.middleware.asgi` and `arcp.middleware.aiohttp` packages attach the WebSocket upgrade to Starlette, FastAPI, Litestar, Quart, or `aiohttp.web` servers.

## API reference

Full API reference — every type, method, and event payload — is in [`docs/`](docs/).

## Versioning and compatibility

This SDK speaks **ARCP v1.1 (draft)**. The SDK follows semantic versioning independently of the protocol; the protocol version it negotiates is shown above and in `session.hello`. A runtime advertising a different ARCP MAJOR is not guaranteed compatible. Feature mismatches degrade gracefully: the effective feature set is the intersection of what the client and runtime advertise, and the SDK will not use a feature outside it.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Protocol questions and proposed changes belong in the [spec repository](https://github.com/agentruntimecontrolprotocol/spec); SDK bugs and feature requests belong here.

## License

Apache-2.0 — see [`LICENSE`](LICENSE).
