# 06 — Examples

Scope: map the TypeScript reference's example tree
([`../../../typescript-sdk/examples/README.md`](../../../typescript-sdk/examples/README.md))
to the Python SDK's `examples/` tree. Inputs: spec
[`draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md);
v1.0→v1.1 features in [`01-spec-delta.md`](01-spec-delta.md); current
SDK reality in [`02-current-audit.md`](02-current-audit.md) §2
(every file under `python-sdk/examples/` is targeted at draft-01
and will be deleted before this plan lands); library picks in
[`03-libraries.md`](03-libraries.md) (Python 3.11+, `asyncio` only,
`pydantic` v2, `websockets`, `structlog`, `httpx` optional under
`jwks` extra). Public-API names below are canonical as of the
[`04-architecture.md`](04-architecture.md) reconciliation pass (see
[`10-synthesis.md` §2.2](10-synthesis.md) for the mapping of the
original placeholders to the names in use here).

## 1. Source count and Python disposition

TS's `examples/README.md` prose says "Twenty-three" but the directory
tree has 22 (9 v1.0 core + 9 v1.1 features + 4 host integrations).
The Python disposition commits to **21** deliverable example
directories. The 22→21 reduction:

- `bun/` — N/A. Bun is a JavaScript runtime; there is no Python
  equivalent listener. **Dropped (−1).**
- `express/` + `fastify/` — both demonstrate "one HTTP server serving
  HTTP routes alongside an ARCP WS upgrade on a single port".
  In Python that surface is one ASGI app (Starlette / FastAPI).
  **Merged into `host_asgi/` (−1).**
- `tracing/` — kept as `host_tracing/`.
- One new Python-native host integration is added: `host_aiohttp/`
  (covers `aiohttp.web` runtime users; the `aiohttp` ecosystem is not
  ASGI-shaped, so the ASGI example does not cover it). This is the
  only example that doesn't trace 1:1 to a TS source row; its
  inclusion makes the host-integration coverage match TS's intent
  (Express+Fastify+Bun were the three Node-host pairings) given that
  ASGI subsumes two of those and `bun` is N/A.

Tally: 9 core + 9 v1.1 + 3 host integrations = **21**. The earlier
stub-figure of "18 new" in `02-current-audit.md` §5 has been corrected
to 21 with the derivation inline; see also
[`10-synthesis.md` §2.1](10-synthesis.md).

### Mapping (21 rows)

Casing rule: Python example directories use `snake_case`. The TS
kebab-case names map mechanically (`submit-and-stream` →
`submit_and_stream`). No mixing.

#### 1a. v1.0 core (9 → 9)

| TS dir                  | Python dir                         | Files                                                                                  | Anchored spec § + one-line demonstration                                                                                                                                                                                                                              | Python idiom this example earns its row on                                                                                                                                                                                                                                       |
| ----------------------- | ---------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `submit-and-stream/`    | `examples/submit_and_stream/`      | `server.py`, `client.py`, `README.md`                                                  | §13.1 / §7.1 / §8.2 — agent emits 7 of 8 reserved event kinds (status, log, thought, metric, tool_call, tool_result, artifact_ref); client awaits the terminal `job.result` and prints `event_seq` per event.                                                       | `async for env in handle.events():` over a typed `Envelope` discriminated union and `match env.payload.kind: case "tool_result": …` instead of TS's `client.on("job.event", cb)` callback.                                                                                       |
| `delegate/`             | `examples/delegate/`               | `server.py`, `client.py`, `README.md`                                                  | §13.2 / §10 — parent agent calls `ctx.delegate(...)`; child inherits `trace_id` and a strict-subset lease; example asserts the relationship in the printed envelopes.                                                                                                | `async with asyncio.TaskGroup() as tg: tg.create_task(...)` for the parent waiting on the child handle, mirroring the structured-concurrency seam called out in [`02-current-audit.md`](02-current-audit.md) §4.                                                                  |
| `resume/`               | `examples/resume/`                 | `server.py`, `client.py`, `README.md`                                                  | §13.3 / §6.3 — client disconnects after seq=2, reconnects with `session.hello.payload.resume = { session_id, resume_token, last_event_seq }`; runtime replays tail with `event_seq > 2`; client asserts the new `resume_token` differs.                              | `contextlib.AsyncExitStack` to scope the two successive `WebSocketTransport` lifetimes so the first one's close is observable before the second connect; `tracemalloc`-free no-leak assertion via the stack's `aclose()`.                                                       |
| `idempotent-retry/`     | `examples/idempotent_retry/`       | `server.py`, `client.py`, `README.md`                                                  | §13.5 / §7.2 — same `(principal, idempotency_key)` returns the same `job_id`; same key + different `agent` raises `DuplicateKeyError`.                                                                                                                              | `pytest.raises`-shaped client-side handling — `try: await client.submit(...) except DuplicateKeyError as e:` — to demonstrate the typed-exception surface from [`01-spec-delta.md`](01-spec-delta.md) §2, not a `str` code compare.                                              |
| `lease-violation/`      | `examples/lease_violation/`        | `server.py`, `client.py`, `README.md`                                                  | §13.4 / §9.3 — an out-of-lease `tool_call` returns a `tool_result` whose `body.error.code == "PERMISSION_DENIED"`; the agent observes, logs, continues; job ends `success`.                                                                                          | `match` on the `tool_result` body's `error` field — `case ToolResultBody(error=ARCPError(code="PERMISSION_DENIED")): …` — earning the row by showing pattern-matching on Pydantic v2 discriminated bodies, not isinstance trees.                                                  |
| `cancel/`               | `examples/cancel/`                 | `server.py`, `client.py`, `README.md`                                                  | §7.4 — client sends `job.cancel { reason }`; agent observes `ctx.signal` (an `asyncio.Event` set immediately before `CancelledError` is raised per [`04-architecture.md`](04-architecture.md) §2) or catches `CancelledError`; runtime emits `job.error { final_status: "cancelled" }`. | The example's agent body raises `asyncio.CancelledError` from inside the agent coroutine when `ctx.signal.is_set()`, demonstrating the **single** cancellation channel decision the audit forces. Client side wraps the `await handle.done` in `with contextlib.suppress(CancelledError):` only on the **timeout** path, not the protocol cancel path. |
| `stdio/`                | `examples/stdio/`                  | `server.py`, `client.py`, `runner.py`, `README.md`                                     | §4.2 / §22 — `client.py` is the parent process; it spawns `server.py` as a child via `asyncio.create_subprocess_exec` and wraps its pipes in `StdioTransport`. `runner.py` is the single-command entrypoint (`python examples/stdio/runner.py`).                       | `async with asyncio.create_subprocess_exec(...)` is **not** a thing in stdlib; the example uses an `AsyncExitStack` that registers `proc.kill` / `await proc.wait()` as the cleanup. This is the **only** example with a `runner.py`, matching TS's single-command exception.    |
| `vendor-extensions/`    | `examples/vendor_extensions/`      | `server.py`, `client.py`, `README.md`                                                  | §8.2 / §9.2 / §15 — agent emits `x-vendor.acme.progress` event kind and requests an `x-vendor.acme.metrics` lease namespace; client shows a naïve handler ignoring unknown kinds and a vendor-aware handler rendering them.                                          | The vendor-aware handler is a plain `if env.payload.kind.startswith("x-vendor.acme."): …` branch ahead of the reserved-kind `match`. The naïve handler uses only `match` with no default arm to make "unknown kinds are silently dropped" syntactically visible.                  |
| `custom-auth/`          | `examples/custom_auth/`            | `server.py`, `client.py`, `README.md`                                                  | §6.1 — a `BearerVerifier` subclass that verifies stateless HMAC-signed `principal.exp.hmac` tokens; bad tokens are rejected with `UNAUTHENTICATED` at handshake.                                                                                                      | `class SignedTokenVerifier(BearerVerifier):` with `async def verify(self, token: str) -> Identity` returning a `pydantic.BaseModel`; demonstrates the abstract-class seam the SDK keeps salvaged from current `auth/bearer.py` per [`02-current-audit.md`](02-current-audit.md) §2. |

#### 1b. v1.1 features (9 → 9)

`session.hello.payload.capabilities.features` in each of these
advertises **only** the feature(s) the row exercises. The
intersection rule (§6.2) then guarantees that an unrelated v1.1 peer
would still negotiate down to v1.0 — the test for "negotiate-down
still works" is implicit in every row.

| TS dir              | Python dir                       | Files                                 | Anchored spec § + one-line demonstration                                                                                                                                                                                                          | Python idiom                                                                                                                                                                                                                              | Advertised `features`                       |
| ------------------- | -------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| `heartbeat/`        | `examples/heartbeat/`            | `server.py`, `client.py`, `README.md` | §6.4 — `session.ping` / `session.pong` keepalive on a 5 s cadence declared in `welcome.heartbeat_interval_sec`; client prints the negotiated interval.                                                                                            | The heartbeat coroutine lives outside the connection's `TaskGroup` per [`02-current-audit.md`](02-current-audit.md) §4 third bullet; client demonstrates this by reading `client.negotiated_features` and asserting `"heartbeat" in` it. | `["heartbeat"]`                             |
| `ack-backpressure/` | `examples/ack_backpressure/`     | `server.py`, `client.py`, `README.md` | §6.5 / §8.2 — client opts into auto-ack but starves it; runtime detects lag and emits `status { phase: "back_pressure" }`.                                                                                                                       | The starved-ack client uses `client = ARCPClient(auto_ack=AckPolicy(every_n=10_000))`; demonstrates that `AckPolicy` is a structured config object (Pydantic model), not a callback.                                                      | `["ack"]`                                   |
| `list-jobs/`        | `examples/list_jobs/`            | `server.py`, `client.py`, `README.md` | §6.6 — `session.list_jobs` filter + cursor pagination; example walks two pages of `limit=2`.                                                                                                                                                      | Two explicit calls: `page1 = await client.list_jobs(filter=ListJobsFilter(status=["running"]), limit=2)`; `page2 = await client.list_jobs(filter=…, limit=2, cursor=page1.next_cursor)` — pagination is **manual cursor follow-up**, matching TS and Phase 4 §5's single-response signature. The typed `ListJobsFilter` model is the demonstration. | `["list_jobs"]`                             |
| `subscribe/`        | `examples/subscribe/`            | `server.py`, `client.py`, `README.md` | §7.6 / §6.6 — Client A submits, Client B discovers via `list_jobs`, calls `client.subscribe(job_id, history=True)`, replays + tails; cross-session cancel from B is denied `PERMISSION_DENIED`.                                                  | Two `ARCPClient` instances inside one `asyncio.TaskGroup`. `await sub.cancel(...)` is wrapped in `pytest.raises`-shape `try/except PermissionDeniedError:` to make the auth assertion visible.                                            | `["list_jobs", "subscribe"]`                |
| `agent-versions/`   | `examples/agent_versions/`       | `server.py`, `client.py`, `README.md` | §7.5 / §12 — three submits: bare name (default resolves), pinned `name@1.2.3`, unregistered `name@9.9.9` raises `AgentVersionNotAvailableError`.                                                                                                  | `client.capabilities.agents` is a typed Pydantic model — the example walks it with `for a in welcome.capabilities.agents: print(a.name, a.versions, a.default)` rather than indexing JSON.                                                | `["agent_versions"]`                        |
| `lease-expires-at/` | `examples/lease_expires_at/`     | `server.py`, `client.py`, `README.md` | §9.5 / §12 — `lease_constraints.expires_at = now + 5s`; agent's `validate_lease_op(now=...)` and the runtime watchdog both trip `LEASE_EXPIRED`.                                                                                                  | `from datetime import datetime, timedelta, UTC` and `expires_at=datetime.now(UTC) + timedelta(seconds=5)` — anchors the ISO-8601-UTC choice from [`01-spec-delta.md`](01-spec-delta.md) §1 row §9.5 in idiomatic `datetime` use, not strings.                                                                                | `["lease_expires_at"]`                      |
| `cost-budget/`      | `examples/cost_budget/`          | `server.py`, `client.py`, `README.md` | §9.6 / §12 — lease grants `USD:1.00`; agent emits `metric { name: "cost.openai", unit: "USD", value: 0.30 }` per iteration; on the 4th call the runtime returns `BUDGET_EXHAUSTED` via `tool_result.body.error`.                                  | The example uses `Decimal` for budget amounts (`from decimal import Decimal`) not `float` — anchors the `currency:decimal` grammar from [`01-spec-delta.md`](01-spec-delta.md) §1 row §9.6 to the only numeric type that won't drift.       | `["cost.budget"]`                           |
| `progress/`         | `examples/progress/`             | `server.py`, `client.py`, `README.md` | §8.2.1 — agent emits `progress { current, total, units, message }`; client renders a text progress bar.                                                                                                                                          | `async for ev in handle.events():` with `match ev.payload.body: case ProgressBody(current=c, total=t): …` — pattern-matching on the typed `TypedDict` bodies from Phase 4 §3 instead of a string-kind compare. Rendering is `sys.stdout.write(f"\\r…")` + `flush()`. | `["progress"]`                              |
| `result-chunk/`     | `examples/result_chunk/`         | `server.py`, `client.py`, `README.md` | §8.4 — agent uses `async with ctx.stream_result() as stream:` writing ~30 chunks; terminal `job.result` carries `result_id` + `result_size`; client reassembles via `async for chunk in handle.chunks()`. Worked sketch in §4 below.             | `async for chunk in handle.chunks(): sys.stdout.buffer.write(chunk.data)` — async iterator, not a callback. Reassembly uses `bytearray` then a single `bytes()` conversion; `result = await handle.done; assert len(blob) == result.result_size`. | `["result_chunk"]`                          |

#### 1c. Host integrations (4 → 3)

| TS dir                | Python dir                  | Files                                              | Anchored spec § + demonstration                                                                                                                              | Python idiom                                                                                                                                                                                                                                                                                                |
| --------------------- | --------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tracing/`            | `examples/host_tracing/`    | `server.py`, `client.py`, `README.md`              | §11 — OTel `ConsoleSpanExporter` on **both** sides; W3C `traceparent` rides `extensions["x-vendor.opentelemetry.tracecontext"]`; same trace spans the wire. | `from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor` configured *only inside `__main__`* per [`03-libraries.md`](03-libraries.md) §7 ("library does not configure a tracer provider"). This is the **only** example with extra stdout noise; tests must exempt it from the stdout-quietness check. |
| `express/` + `fastify/` | `examples/host_asgi/`     | `server.py` (Starlette app), `client.py`, `README.md` | §4.1 — one ASGI app serving HTTP routes (`GET /health`) alongside the ARCP WebSocket upgrade at `/arcp`; `allowed_hosts` Host-header guard.                | Starlette `Mount("/arcp", ARCPWSEndpoint(...))` with a sibling `Route("/health", ...)`; this single example covers the surface that TS splits across `express/` and `fastify/`. Pino-style structured-log demonstration is folded in via `structlog.contextvars.bind_contextvars(request_id=...)`.            |
| (new)                 | `examples/host_aiohttp/`    | `server.py`, `client.py`, `README.md`              | §4.1 — `aiohttp.web.Application` mounting ARCP via an `aiohttp.web.WebSocketResponse` upgrade handler; demonstrates that the wire is host-framework-agnostic. | The example exists because `aiohttp` is not ASGI-compatible and a non-trivial slice of Python async-web users run it. The `Transport` adapter wraps `aiohttp.web.WebSocketResponse.{send_str, receive}` to satisfy the same `Transport` protocol the ASGI example uses, proving the seam is portable.        |

## 2. Common shape

Every example follows the same six rules. A reader who spot-checks
one can predict the others.

1. **Two terminals.** Each example is launched as
   ```sh
   python examples/<name>/server.py    # terminal 1
   python examples/<name>/client.py    # terminal 2
   ```
   matching TS's convention. `examples/` is **not** an installable
   subpackage of `arcp` — the `python -m arcp.examples.<name>` route
   was considered and rejected because it requires either shipping
   examples in the wheel (size + import-side-effect risk) or a
   namespace-package gymnastic that buys nothing over a clear
   "examples live in the repo, not the published package" rule.
   The one exception is `stdio/`, which has a `runner.py` that
   spawns its own server (single-command, matching TS's `stdio/`).
2. **Env-var overrides.** Three env vars override defaults, matching
   TS: `ARCP_DEMO_PORT` (server bind / client connect port),
   `ARCP_DEMO_URL` (full client URL; takes precedence over `_PORT`
   for the client), `ARCP_DEMO_TOKEN` (bearer token, default
   `"demo-token"`, both sides). No other env vars.
3. **Port allocation.** Default ports are unique per example so
   multiple examples can run in parallel in CI. Reuse TS's
   allocation directly — same default port per matching example —
   so a contributor switching between SDKs doesn't have to remember
   two port maps:

    | Default port | Example                                                                                                |
    | ------------ | ------------------------------------------------------------------------------------------------------ |
    | 7878         | `delegate/`                                                                                            |
    | 7879         | `submit_and_stream/`                                                                                   |
    | 7880         | `resume/`                                                                                              |
    | 7881         | `idempotent_retry/`                                                                                    |
    | 7882         | `lease_violation/`                                                                                     |
    | 7883         | `cancel/`                                                                                              |
    | 7884         | `vendor_extensions/`                                                                                   |
    | 7885         | `heartbeat/`                                                                                           |
    | 7886         | `ack_backpressure/`                                                                                    |
    | 7887         | `list_jobs/`                                                                                           |
    | 7888         | `subscribe/`                                                                                           |
    | 7889         | `agent_versions/`                                                                                      |
    | 7890         | `lease_expires_at/`                                                                                    |
    | 7891         | `cost_budget/`                                                                                         |
    | 7892         | `progress/`                                                                                            |
    | 7893         | `result_chunk/`                                                                                        |
    | 7894         | `custom_auth/`                                                                                         |
    | 7895         | `host_tracing/`                                                                                        |
    | 7896         | `host_asgi/`                                                                                           |
    | 7897         | `host_aiohttp/` (was TS `fastify/`'s slot; ASGI takes Express's 7896 since it covers Express's surface) |
    | n/a          | `stdio/` (no socket)                                                                                   |
4. **Transport pairing.** The rule is: **no example uses
   `MemoryTransport`**. `MemoryTransport` is a test seam (see
   [`02-current-audit.md`](02-current-audit.md) §2 row
   `transport/in_memory.py`), not an example seam — the point of an
   example is to exercise a real network path. Specifically:
    - `stdio/` uses `StdioTransport` (parent ↔ child pipes).
    - Every other example uses `WebSocketTransport` (loopback,
      127.0.0.1). The three host integrations (`host_tracing/`,
      `host_asgi/`, `host_aiohttp/`) use the framework-supplied WS
      upgrade and adapt it to the `Transport` protocol from
      [`02-current-audit.md`](02-current-audit.md) §2 row
      `transport/base.py`.
5. **Exit codes.** The **client** exits 0 on success and non-zero
   on protocol error. "Success" is per-example, listed below. The
   client never silently swallows an `ARCPError`; any uncaught
   exception in `main()` propagates to `asyncio.run` which exits
   1. Servers run until SIGINT/SIGTERM and exit 0 on clean
   shutdown; their exit code is not load-bearing (only the client's
   is checked by the CI runner).

    | Example                | Client success =                                                                                                                                       |
    | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `submit_and_stream/`   | `result.final_status == "success"` and ≥ 7 events observed                                                                                            |
    | `delegate/`            | parent and child `final_status == "success"`; child `trace_id == parent.trace_id`                                                                     |
    | `resume/`              | second connection returns a `resume_token` differing from the first; replayed envelope seqs all > `last_event_seq`                                    |
    | `idempotent_retry/`    | second submit returns same `job_id`; third submit (mutated agent) raises `DuplicateKeyError`                                                          |
    | `lease_violation/`     | `tool_result.body.error.code == "PERMISSION_DENIED"`; terminal `final_status == "success"`                                                            |
    | `cancel/`              | terminal `job.error { final_status: "cancelled" }` arrives within 30 s of `client.cancel(job_id)` (§7.4)                                              |
    | `stdio/`               | child exits 0 after parent disconnects; result `final_status == "success"`                                                                            |
    | `vendor_extensions/`   | naïve receiver ignored ≥ 1 unknown kind; vendor-aware receiver rendered ≥ 1 `x-vendor.acme.progress`                                                  |
    | `custom_auth/`         | one valid-token submit succeeds; one invalid-token connect raises `AuthenticationError` (mapped from `UNAUTHENTICATED`)                               |
    | `heartbeat/`           | client received `welcome.heartbeat_interval_sec == 5`; client sent ≥ 2 pongs in the job's lifetime                                                    |
    | `ack_backpressure/`    | client observed ≥ 1 `status { phase: "back_pressure" }` envelope                                                                                      |
    | `list_jobs/`           | two pages returned; total job count = 3; `next_cursor` is `None` only on the last page                                                                |
    | `subscribe/`           | Client B's history replay length > 0; live tail observed ≥ 1 event; Client B's `cancel(...)` raised `PermissionDeniedError`                          |
    | `agent_versions/`      | bare-name and `@1.2.3` submits each return a `job_id`; `@9.9.9` raises `AgentVersionNotAvailableError`                                                |
    | `lease_expires_at/`    | terminal `job.error { code: "LEASE_EXPIRED" }` arrives                                                                                                |
    | `cost_budget/`         | one `tool_result.body.error.code == "BUDGET_EXHAUSTED"` observed; remaining metrics monotone-decreasing                                               |
    | `progress/`            | ≥ 5 `progress` events observed; final `current == total`                                                                                              |
    | `result_chunk/`        | reassembled `len(blob) == result.result_size`; chunk count == 30                                                                                      |
    | `host_tracing/`        | ≥ 1 client span and ≥ 1 server span share the same `trace_id`; printed to stdout                                                                      |
    | `host_asgi/`           | `GET /health` returns `{"ok": true, "request_id": "..."}`; the WS submit returns `final_status == "success"`                                          |
    | `host_aiohttp/`        | same shape as `host_asgi/` but `GET /health` is served by `aiohttp.web`                                                                               |

6. **No silent `INTERNAL_ERROR`.** Any client-side catch of
   `ARCPError` re-raises after logging, except in `lease_violation/`,
   `idempotent_retry/`, `subscribe/`, `agent_versions/`, and
   `cost_budget/` where catching a specific typed exception is the
   demonstration. Those four catch the specific subclass
   (`PermissionDeniedError`, `DuplicateKeyError` /
   `PermissionDeniedError`, `AgentVersionNotAvailableError`,
   `BudgetExhaustedError`) — never the bare `ARCPError` base.

## 3. Cancellation and lifetime rules every example obeys

The examples are also the canonical readable reference; their
idioms become the SDK's documented Python style. The rules below
are normative for every row in §1.

1. **Client lifetime is `async with`.** Every `client.py` opens its
   client as
   ```python
   async with contextlib.aclosing(ARCPClient(client=info, auth_scheme="bearer", token=TOKEN)) as client:
       transport = await WebSocketTransport.connect(url)
       await client.connect(transport)
       ...
   ```
   The `ARCPClient(...)` constructor is plain (per Phase 4 §5.1); the
   transport is passed explicitly to `client.connect(transport)`; the
   `contextlib.aclosing` wrapper guarantees `await client.close()` runs
   on the exception path so the read pump and write pump finalize
   cleanly. The TS examples' explicit `await client.close()` at the end
   of `main()` is converted to `async with` because Python's exception
   path otherwise leaks the `TaskGroup` from Phase 4 §2.

2. **Transports are scoped too.** Where the example needs an
   explicit `WebSocketTransport` (e.g. `resume/` constructs two
   successive transports for the same session), each transport is
   itself an async context manager — `async with
   WebSocketTransport.connect(url) as transport:` — and the
   `client.connect(transport)` call lives inside that scope.

3. **More than one task → `TaskGroup`.** Any example that spawns
   more than one concurrent task (notably `delegate/`, `subscribe/`,
   `cancel/`, `host_tracing/` if you count the OTel flush task, and
   the `stdio/` runner) uses `async with asyncio.TaskGroup() as
   tg:` followed by `tg.create_task(...)`. No raw
   `asyncio.create_task` survives without explicit cleanup. The
   TS reference uses ad-hoc `Promise.all`; the Python idiom is
   `TaskGroup` because of the cancellation-propagation properties
   [`02-current-audit.md`](02-current-audit.md) §4 calls out, and
   the examples have to model that.

4. **Cancellation paths match the test shape.** The
   conformance tests (Phase 7) will assert cancel semantics with
   `with pytest.raises(asyncio.CancelledError):`. The agent
   coroutine in `cancel/server.py` therefore raises plain
   `asyncio.CancelledError` (re-raised from the natural unwind of
   `await ctx.signal.wait(); ...` or from any awaited operation when
   the runtime cancels the job's `TaskGroup`), not a custom exception.
   This is the **single** cancellation channel from Phase 4 §2.
   `subscribe/server.py` similarly does not swallow `CancelledError`
   in its subscriber fan-out.

5. **Heartbeat tasks are not children of the connection
   `TaskGroup`.** `heartbeat/` documents this in its `README.md`
   because [`02-current-audit.md`](02-current-audit.md) §4 third
   bullet makes it a load-bearing constraint: a heartbeat timeout
   raising `HeartbeatLostError` inside a `TaskGroup` would cancel
   sibling tasks, including the job emit pump. The example shows
   the heartbeat loop running off the session context with the
   loss signaled via an `asyncio.Future`, not a raised exception
   into the group.

## 4. Worked sketch: `result_chunk/`

Sketch only — actual code lives in `examples/result_chunk/`. The
TS reference is
[`typescript-sdk/examples/result-chunk/client.ts`](../../../typescript-sdk/examples/result-chunk/client.ts)
and `server.ts`. Signatures match
[`04-architecture.md` §5](04-architecture.md) verbatim.

Client side (`examples/result_chunk/client.py`, abbreviated):

```python
# Sketch only — actual code lives in examples/result_chunk/client.py
client = ARCPClient(client=info, auth_scheme="bearer", token=TOKEN)
async with contextlib.aclosing(client):
    transport = await WebSocketTransport.connect(url)
    await client.connect(transport)
    handle = await client.submit(agent="report-builder", input={"chunks": 30})
    blob = bytearray()
    async for chunk in handle.chunks():        # NOT client.on("result_chunk", cb)
        blob.extend(chunk.data)
    result = await handle.done                 # awaitable property; carries result_id, result_size
    assert result.final_status == "success"
    assert len(blob) == result.result_size
```

Server side (`examples/result_chunk/server.py`, abbreviated):

```python
# Sketch only — actual code lives in examples/result_chunk/server.py
async def report_builder(input, ctx):
    async with ctx.stream_result() as stream:      # __aenter__/__aexit__ on ResultStream (Phase 4 §5.4)
        for i in range(1, 31):
            await stream.write(f"Section {i}: ...\n".encode())
        # __aexit__ calls stream.close(summary=...) automatically;
        # explicit close() with an override is allowed:
        await stream.close(summary="report with 30 chunks")
```

The async-iterator surface on the client (`async for chunk in
handle.chunks()`) and the async-context-manager surface on the
server (`async with ctx.stream_result() as stream`) are the two
specific Python idioms the example exists to demonstrate. The TS
reference uses a callback subscription on the client
(`client.on("job.event", cb)`) and a non-CM stream object on the
server (`const stream = ctx.streamResult(); await
stream.finalize(...)`); the Python translations are deliberately
*not* literal because both literal translations would be poor
Python:

- A callback registration loses the type narrowing that an
  `async for` provides over a `Chunk` (the iterator yields
  `Chunk`, not `Envelope`, so `chunk.chunk_seq` is typed without
  a discriminated-union check).
- A non-CM `stream.finalize()` makes "the stream stays open if the
  agent raises" possible; the `async with` makes that a syntactic
  impossibility and ensures `more=False` is sent even on the
  exception path.

## 5. Demands per category

- **v1.0 core (9 rows).** Must work without negotiating any v1.1
  feature. They exercise the realigned wire from
  [`02-current-audit.md`](02-current-audit.md) §1 — and nothing
  else. Their `session.hello.payload.capabilities.features` is
  `[]`. If they break when a v1.1-only feature is added to the
  intersection, that is a bug in the v1.1 implementation, not the
  example.
- **v1.1 feature (9 rows).** Each `session.hello.payload.capabilities.features`
  advertises **only** the feature(s) the row exercises (see the
  "Advertised `features`" column in §1b). This makes the
  intersection-rule from §6.2 implicit: a runtime offering more
  features than the example needs will not push them onto the
  example client. Conformance Phase 7 then has a free property test
  ("every v1.1 example still passes when the runtime additionally
  advertises {everything else}").
- **Host integrations (3 rows).** All three use a real WebSocket
  transport. `host_tracing/` is the **only** example that emits
  span-export noise on stdout; the CI runner's
  stdout-quietness check (Phase 7) explicitly exempts it. The
  ASGI and aiohttp examples have a sibling HTTP route
  (`GET /health`) to demonstrate that the framework's HTTP
  pipeline coexists with ARCP on one port; the client hits
  `/health` first and the WS second to assert both.

## 6. What the TS list has 22 of but Python should not include verbatim

Mark-up of every TS dir against the Python plan:

| TS dir                  | Translates cleanly? | Python disposition                                                                                                            |
| ----------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `submit-and-stream/`    | yes                 | `examples/submit_and_stream/`                                                                                                 |
| `delegate/`             | yes                 | `examples/delegate/`                                                                                                          |
| `resume/`               | yes                 | `examples/resume/`                                                                                                            |
| `idempotent-retry/`     | yes                 | `examples/idempotent_retry/`                                                                                                  |
| `lease-violation/`      | yes                 | `examples/lease_violation/`                                                                                                   |
| `cancel/`               | yes                 | `examples/cancel/`                                                                                                            |
| `stdio/`                | yes                 | `examples/stdio/` (only example with a `runner.py`)                                                                           |
| `vendor-extensions/`    | yes                 | `examples/vendor_extensions/`                                                                                                 |
| `custom-auth/`          | yes                 | `examples/custom_auth/`                                                                                                       |
| `heartbeat/`            | yes                 | `examples/heartbeat/`                                                                                                         |
| `ack-backpressure/`     | yes                 | `examples/ack_backpressure/`                                                                                                  |
| `list-jobs/`            | yes                 | `examples/list_jobs/`                                                                                                         |
| `subscribe/`            | yes                 | `examples/subscribe/`                                                                                                         |
| `agent-versions/`       | yes                 | `examples/agent_versions/`                                                                                                    |
| `lease-expires-at/`     | yes                 | `examples/lease_expires_at/`                                                                                                  |
| `cost-budget/`          | yes                 | `examples/cost_budget/`                                                                                                       |
| `progress/`             | yes                 | `examples/progress/`                                                                                                          |
| `result-chunk/`         | yes                 | `examples/result_chunk/`                                                                                                      |
| `tracing/`              | yes                 | `examples/host_tracing/`                                                                                                      |
| `express/`              | partial             | folded into `examples/host_asgi/` (Starlette serves the same "HTTP + WS-upgrade on one port" surface)                         |
| `fastify/`              | partial             | folded into `examples/host_asgi/` (same surface as Express in Python; pino-style structured logs are demonstrated via `structlog`) |
| `bun/`                  | no                  | **N/A.** Bun is JS-runtime-specific; there is no Python equivalent listener. Dropped.                                         |
| (new in Python)         | —                   | `examples/host_aiohttp/` added because `aiohttp` is not ASGI-compatible and ASGI alone doesn't cover its user base.            |

Final count: TS 22 dirs → Python **21 dirs**.
[`02-current-audit.md`](02-current-audit.md) §5 is reconciled to
"14 old → 21 new" with the +3 derivation inline (`host_aiohttp/`
is genuinely new; `host_asgi/` absorbs two TS rows; `bun/` is
dropped). This file is the source of truth for that count;
[`10-synthesis.md` §2.1](10-synthesis.md) carries the audit trail.

## 7. Names anchored to `04-architecture.md`

The post-reconciliation API names that drive every row in §1 and the
worked sketch in §4:

- Client construction: plain constructor `ARCPClient(*, client, auth_scheme, token, …)`; transport passed explicitly as `await client.connect(transport)`.
- Termination: `await handle.done` — awaitable property on `JobHandle`, not `await handle.result`.
- Cancellation channel: `ctx.signal: asyncio.Event` (set before `CancelledError`), not `ctx.cancelled`.
- `list_jobs`: single `SessionJobsPayload` response; cursor pagination is manual follow-up calls, not an async iterator.
- `subscribe`: keyword-only `history` and `from_event_seq` per Phase 4 §5.1.
- Streamed result writer: `async with ctx.stream_result() as stream:` (`ResultStream` is an async context manager — Phase 4 §5.4).
- Streamed result reader: `async for chunk in handle.chunks():` (async iterator) plus `await handle.collect_chunks()` convenience.
- Lease-op clock injection: `validate_lease_op(... , now=...)` on `_runtime/lease.py`.
- `BearerVerifier.verify` returns an `Identity` model (Phase 4 §5 mirror of TS `BearerVerifier.verify`).

Any later signature change in Phase 4 §5 is a coordinated edit to both
files; this document is no longer racing.
