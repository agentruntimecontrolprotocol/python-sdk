# 04 — Architecture: Package Layout, Type Model, Async Model

Phase 4 of 10. Reviewer reads in ≤8 minutes. Every claim cites a spec §, a
TS path under `typescript-sdk/`, a current-Python path from
[`02-current-audit.md`](./02-current-audit.md), or — where Phase 3 has
not yet landed — a named library pick this document commits to.

**Phase 3 alignment.** [`03-libraries.md`](./03-libraries.md) pins
Python **≥3.11** (§14: `TaskGroup`, `asyncio.timeout`,
`ExceptionGroup`, `Self`), **pydantic v2** (§1: discriminated unions on
`job.event.payload.kind`, `model_config(extra="ignore")` for §5.1
unknown-field rule), **stdlib asyncio** (§4: rejects `anyio`),
**`python-ulid`** for IDs (§6), **`opentelemetry-api`** API-only
(§7), **`aiosqlite`** (§9), **`structlog`** (§5), **`click`** (§10),
**`pyright --strict`** (§12), `httpx` as a **conditional** dep behind
the `jwks` extra (§3). This document's §3 type-model picks, §1's
`_ulid.py` module, and §2's concurrency model are all consistent with
those choices. The single deferred decision — PEP 695 generic syntax —
remains off because Phase 3 §14 pins 3.11 (PEP 695 requires 3.12);
PEP 585 / `typing.Generic[T]` is used throughout §5's signatures.

## 1. Module tree under `src/arcp/`

Single importable `arcp` package — not four sub-packages mirroring
TS `@arcp/{core,client,runtime,sdk}`. The TS split exists because npm
ships each package independently; PyPI offers no analogous distribution
benefit when one wheel covers all surfaces, and the user-facing API
fits in four namespaces (`arcp`, `arcp.client`, `arcp.runtime`,
`arcp.middleware`). Public/private separation is enforced by leading
underscores on **module** names, not by package boundaries. The shape
below mirrors the disposition table in
[`02-current-audit.md` §2](./02-current-audit.md): every node is either
flagged **Salvage** (interface stays, body rewritten elsewhere) or
explicitly justified as a new module.

```
src/arcp/
  __init__.py                      Public re-exports only. Enumerated in §6.
  py.typed                         PEP 561 marker. Salvage of current `src/arcp/py.typed`.

  _version.py                      PROTOCOL_VERSION="1", IMPL_VERSION, V1_1_FEATURES tuple,
                                   intersect_features(a,b) helper. Mirrors typescript-sdk/
                                   packages/core/src/version.ts. Replaces the broken
                                   PROTOCOL_VERSION="1.0" in src/arcp/version.py.
  _envelope.py                     8-field §5.1 envelope + extensions, pydantic v2 model,
                                   `from_wire` / `to_wire`, passthrough of unknown top-level
                                   keys. Replaces src/arcp/envelope.py (17-field draft-01 shape).
  _errors.py                       ARCPError hierarchy (§4 below) + `error_from_wire(code)`
                                   registry. Replaces src/arcp/errors.py (20 gRPC codes).
  _extensions.py                   x-vendor.* / arcpx.* classifier. Salvage of
                                   src/arcp/extensions.py.
  _logger.py                       structlog adapter. New (current code uses ad-hoc
                                   logging in src/arcp/runtime/*).
  _ulid.py                         Message-id / job-id / session-id minting (ULID/UUIDv7).
                                   New; mirrors typescript-sdk/packages/core/src/util/ulid.ts.

  _auth/
    __init__.py                    Empty package marker. Salvage.
    bearer.py                      BearerVerifier protocol + StaticBearerVerifier.
                                   Salvage of src/arcp/auth/bearer.py.
    jwt.py                         JWTVerifier. Salvage of src/arcp/auth/jwt.py.

  _messages/
    __init__.py                    Type → pydantic model registry. Rewrite of
                                   src/arcp/messages/__init__.py.
    session.py                     session.hello / welcome / error / bye / ping / pong /
                                   ack / list_jobs / jobs. Mirrors typescript-sdk/
                                   packages/core/src/messages/session.ts. Rewrite of
                                   src/arcp/messages/session.py.
    execution.py                   job.submit / accepted / cancel / event / result / error /
                                   subscribe / subscribed / unsubscribe, the 10 event
                                   kinds incl. progress (§8.2.1) and result_chunk (§8.4),
                                   Lease, LeaseConstraints, parse_agent_ref,
                                   parse_budget_amount. Mirrors typescript-sdk/packages/
                                   core/src/messages/execution.ts. Rewrite of
                                   src/arcp/messages/execution.py. Note:
                                   src/arcp/messages/{streaming,subscriptions,human,
                                   permissions,artifacts,telemetry}.py are deleted per
                                   02-current-audit.md §2.

  _transport/
    __init__.py                    Salvage.
    base.py                        Transport protocol (send/recv/close/is_closed) +
                                   TransportClosed. Salvage of src/arcp/transport/base.py
                                   verbatim — it already declares the right shape (see §5).
    in_memory.py                   MemoryTransport + pair_memory_transports. Salvage of
                                   src/arcp/transport/in_memory.py.
    stdio.py                       Newline-delimited JSON. Salvage of src/arcp/transport/
                                   stdio.py.
    websocket.py                   `websockets` client + server primitive. Salvage of
                                   src/arcp/transport/websocket.py; write-side backpressure
                                   measurement added per 02-current-audit.md §4.

  _store/
    __init__.py                    Salvage.
    eventlog.py                    aiosqlite event log; adds session-scoped event_seq
                                   column + read_since_seq + ack-aware GC. Rewrite of
                                   src/arcp/store/eventlog.py (schema changes; body shape
                                   carries).
    schema.sql                     New DDL. Rewrite of src/arcp/store/schema.sql.
    idempotency.py                 In-memory (principal, key) → JobId map with TTL sweep.
                                   New; carved out of the old eventlog.py
                                   idempotency_results table.

  _runtime/
    __init__.py                    Empty marker.
    server.py                      ARCPRuntime (a.k.a. ARCPServer): accept(transport),
                                   register_agent / register_agent_version /
                                   set_default_agent_version, dispatch table, agent
                                   inventory, list_jobs / subscribe / ack / ping handlers,
                                   lease-expiry watchdog spawn. Rewrite of
                                   src/arcp/runtime/server.py. Mirrors typescript-sdk/
                                   packages/runtime/src/server.ts.
    session.py                     SessionContext: negotiated_features, next_event_seq,
                                   record_ack, send (with subscriber fan-out), heartbeat
                                   ticker. Rewrite of src/arcp/runtime/session.py.
    job.py                         Job: state machine, apply_cost_metric, emit_result /
                                   emit_error / emit_event_kind, agent_ref;
                                   JobContext (signal, log, progress, metric, tool_call,
                                   stream_result, budget, lease, delegate).
                                   Rewrite of src/arcp/runtime/job.py. Mirrors
                                   typescript-sdk/packages/runtime/src/job.ts.
    lease.py                       validate_lease_shape, validate_lease_op
                                   (now-injectable), is_lease_subset (with
                                   parent_budget_remaining), assert_lease_constraints_subset,
                                   parse_budget_amount, initial_budget_from_lease,
                                   canonicalize_target, compile_glob. Rewrite of
                                   src/arcp/runtime/lease.py. Mirrors typescript-sdk/
                                   packages/runtime/src/lease.ts.
    pending.py                     PendingRegistry keyed by request_id (envelope `id`).
                                   Salvage of src/arcp/runtime/pending.py with key rename
                                   per 02-current-audit.md §2.
                                   (src/arcp/runtime/{stream,subscription,artifact}.py
                                   are deleted.)

  _client/
    __init__.py                    Empty marker.
    client.py                      ARCPClient: connect / resume / submit / cancel_job /
                                   list_jobs / subscribe / ack / close, autoAck timer,
                                   pong responder, chunk accumulator (JobHandle.chunks()),
                                   negotiated_features / has_feature. Rewrite of
                                   src/arcp/client/client.py. Mirrors typescript-sdk/
                                   packages/client/src/client.ts.
    handles.py                     JobHandle, JobSubscription, AckController.
                                   New (carved out of the conflated dispatch + state in
                                   the current src/arcp/client/handlers.py).

  client/                          Public façade. Re-exports ARCPClient, JobHandle,
    __init__.py                    JobSubscription. Nothing else.
  runtime/                         Public façade. Re-exports ARCPRuntime, JobContext,
    __init__.py                    Agent, BearerVerifier, StaticBearerVerifier.

  middleware/                      Phase 5 owns these. Their import surface is fixed here
    __init__.py                    so Phase 4's public re-exports compile against
                                   placeholder stubs.
    asgi.py                        ASGI adapter. Public symbol: arcp_asgi_app(runtime,
                                   *, allowed_hosts=None) -> ASGIApp. Mirrors
                                   typescript-sdk/packages/middleware/node/. New module.
    aiohttp.py                     aiohttp adapter. Public symbols:
                                   arcp_aiohttp_handler(runtime, *, allowed_hosts=None)
                                   and serve_arcp_aiohttp(runtime, *, host, port, path,
                                   allowed_hosts=None). New module.
    otel.py                        OTel transport wrapper. Public symbol:
                                   with_tracing(inner, *, tracer, send_span_name=None,
                                   recv_span_name=None) -> Transport. Adds v1.1 span
                                   attrs arcp.lease.expires_at and arcp.budget.remaining.
                                   Mirrors typescript-sdk/packages/middleware/otel/.
                                   New module.

  (Examples live at the repo root in examples/, NOT as a subpackage of
  arcp; see 06-examples.md §2 rule 1 for the wheel-size / import-side-
  effect rationale.)

  cli.py                           Public Click entrypoint (serve, submit, tail, replay).
                                   Rewrite of src/arcp/cli.py. Surface mirrors the TS
                                   bin in typescript-sdk/packages/sdk/src/cli.ts.
```

Two structural calls worth defending against the TS layout.

**Why no separate `arcp.core` package.** TS isolates `@arcp/core` so
`@arcp/client` and `@arcp/runtime` users don't transitively bundle the
opposite side. Python wheel install has no such overhead — pyright/mypy
see one namespace either way — so the `_messages/` / `_envelope.py` /
`_errors.py` modules sit at the package root, prefixed `_` to signal
private. Senior reviewers verify the boundary by `grep -rn "from arcp\._"
src/arcp/{client,runtime,middleware}/__init__.py` returning **only**
`from arcp._<x> import …` lines that map to the §6 re-export list.

**Why `arcp.middleware` is in scope here.** Phase 5 owns the contents,
but their **import paths** (`arcp.middleware.asgi`,
`arcp.middleware.aiohttp`, `arcp.middleware.otel`) are stamped here so
that the public façade in `arcp.runtime/__init__.py` and the
`pyproject.toml` `[project.entry-points]` table can be authored before
Phase 5. The TS reference scatters middleware across `@arcp/node`,
`@arcp/express`, `@arcp/fastify`, `@arcp/hono`, `@arcp/bun`,
`@arcp/middleware-otel` (`typescript-sdk/CONFORMANCE.md` "Host
integrations"). Python's web ecosystem is narrower; ASGI covers Starlette,
FastAPI, Quart, Litestar, and Sanic via the single
`scope["type"] == "websocket"` contract, and aiohttp is the lone outlier.
Two adapters cover everything TS needs five for. OTel stays separate.

## 2. Concurrency model

**One `asyncio.TaskGroup` per session lifetime.** Both `ARCPClient.connect`
and `ARCPRuntime.accept(transport)` open an `async with
asyncio.TaskGroup() as tg:` block scoped to a single `SessionContext`.
Inside that block the session opens four explicit children:

| Child task        | Owner module               | Lifetime                                                                                                                                          |
| ----------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| read pump         | `_runtime/session.py` (server side); `_client/client.py` (client side) | `await transport.recv()` loop; exits on `TransportClosed` or on `session.bye`. |
| write pump        | same                        | drains an `asyncio.Queue[Envelope]` and `await transport.send(env)`; exits when the queue is closed.                                              |
| heartbeat ticker  | `_runtime/session.py`       | spawned only when `heartbeat ∈ negotiated_features` (§6.4). Sends `session.ping` on idle, observes inbound liveness, sets a non-TaskGroup signal on detection (see "Heartbeat" below). |
| lease watchdog    | `_runtime/server.py:run_handler` (one per running job) | one task per `Job` when `lease_expires_at ∈ negotiated_features` (§9.5); sleeps to `expires_at`, fires `LEASE_EXPIRED` envelope via the job's `emit_error`. |

The agent coroutine itself is **not** a child of the session TaskGroup
— it is a child of the **job's** TaskGroup, which is in turn a child of
the session's. This two-level nesting is what makes "cancel one job
without tearing down the session" trivially expressible: cancel the
inner `TaskGroup`, the outer survives. TS's `AbortController` per Job
(`typescript-sdk/packages/runtime/src/job.ts:abortController`) encodes
the same containment without structured concurrency; Python gets it for
free.

**Cancellation channel: `asyncio.CancelledError` only — `ctx.signal`
exposes an `asyncio.Event`, but cancel is propagated via
`CancelledError`.** Per [`02-current-audit.md` §4 row 1](./02-current-audit.md),
TS `AbortSignal` is not equivalent to `asyncio.CancelledError`. The
audit calls out two options; this document picks
**propagate `CancelledError` into the agent coroutine** for the cancel
path. Rationale: structured concurrency under `TaskGroup` already unwinds
the stack and runs `finally` blocks; supplying an `Event` instead would
require every agent to poll, break the "agents look like normal async
functions" property the TS reference upholds, and break interaction with
stdlib primitives (`asyncio.wait_for`, `asyncio.timeout`). `ctx.signal`
is **also** exposed (as an `asyncio.Event` set on cancel) for agents
that prefer poll-style cooperation — but it is set **before**
`CancelledError` is raised, never as a substitute. The seam:

> `Job.cancel(reason)` sets `self.signal_event` and then calls
> `self._task_group.cancel()` (which raises `CancelledError` in every
> child task of the job's TaskGroup at the next checkpoint).

**Heartbeat is NOT a child of the session TaskGroup.** Per
[`02-current-audit.md` §4 row 4](./02-current-audit.md), if the heartbeat
loop is a TaskGroup child and raises `HeartbeatLostError`, the TaskGroup
cancels every sibling — including the read pump and any running job's
emit pump — which would terminate jobs on heartbeat loss, violating
spec §6.4 ("The runtime MUST NOT terminate jobs on heartbeat loss; the
session continues to exist for the resume window"). The heartbeat
ticker is launched via `asyncio.create_task()` **outside** the TaskGroup
and writes its outcome to `SessionContext.heartbeat_outcome:
asyncio.Future[None]`. The session main loop observes that Future
alongside the read pump; if set with `HeartbeatLostError`, it initiates
**transport close** but allows the jobs `TaskGroup` to drain naturally
(its tasks live on the runtime-global job pool, not under the session's
TaskGroup). Re-stated as one invariant:

> A `HeartbeatLostError` MUST close the transport. It MUST NOT
> propagate into any job's `TaskGroup`. The session record persists
> until `resume_window_sec` elapses (§6.3).

**`event_seq` atomicity.** Per
[`02-current-audit.md` §4 row 3](./02-current-audit.md), §8.3 requires
the counter to be session-scoped across concurrent jobs. The seam: the
single emit primitive on `SessionContext` is

```
def _stamp_and_emit(self, env: Envelope) -> None:
    env.event_seq = self._next_event_seq()   # bumps counter
    self._send_queue.put_nowait(env)         # non-await dispatch
```

`_next_event_seq` and `put_nowait` are both **non-coroutine**; the whole
primitive contains no `await`. The write pump is the only task that
calls `transport.send(env)`, so the actual I/O is serialized by the
queue, and the counter increments happen in source order. The
**invariant** stated for Phase 7's property-test plan:

> Between observing `self._event_seq` and pushing the envelope onto
> `self._send_queue`, no `await` may execute. Any new emit path MUST
> route through `_stamp_and_emit`; direct `transport.send(...)` of
> seq-bearing envelopes is forbidden.

`asyncio` is single-threaded by default, so a context switch is only
possible at an `await` boundary. The invariant above eliminates that
boundary inside the stamp+enqueue step. Property test (Phase 7):
generate N concurrent jobs each emitting M events; assert the merged
sequence is `[1..N*M]` exactly.

**anyio: ruled out.** Per Phase-3 assumption above, `asyncio` only;
`trio` interop is not in scope.

## 3. Type model — wire envelopes vs event bodies

**Wire envelopes use pydantic v2 `BaseModel`.** Mirrors zod schemas at
`typescript-sdk/packages/core/src/envelope.ts:BaseEnvelopeSchema` and
the per-message schemas under
`typescript-sdk/packages/core/src/messages/{session,execution}.ts`. pydantic
v2 gives (a) recursive validation matching zod's `.refine`, (b) discriminated
unions matching zod's `z.discriminatedUnion("type", [...])`, (c)
`model_config = ConfigDict(extra="allow")` to preserve unknown top-level
fields verbatim per §5.1's "ignore unknown" + §15's vendor-extension
round-trip rule. Each wire model is **frozen** (`frozen=True`) and
**slotted** is not necessary on pydantic v2 (it generates `__slots__`-free
`BaseModel`s by design); when Phase 3 commits, a `dataclass`-backed
alternative is `@pydantic.dataclasses.dataclass(frozen=True, slots=True)`
— that swap is mechanical.

**Event bodies use TypedDict.** The ten reserved kinds (§8.2 + v1.1
`progress` / `result_chunk`) are dispatched on `payload.kind` after the
envelope has already validated. Once the kind is known, the body is a
small structurally-typed dict; pydantic on the inner body adds two
allocations per emitted event with no real validation benefit (§8.4
explicitly anticipates ≥1 chunk per MB of streamed output, so hot-path
allocations matter). `TypedDict` gives pyright static checking at the
agent's `ctx.metric({...})` call site, costs nothing at runtime, and
round-trips through `dict[str, Any]` cleanly. The seam: `_messages/
execution.py` exports both an `EventKindBody = Union[LogBody,
ThoughtBody, ToolCallBody, ToolResultBody, StatusBody, MetricBody,
ArtifactRefBody, DelegateBody, ProgressBody, ResultChunkBody]` for the
public surface and a `parse_job_event_body(kind: str, body: dict) ->
EventKindBody` validator that **does** use pydantic — invoked only on
inbound from the wire, not on agent-emitted outbound. This matches TS's
`parseJobEventBody` in `typescript-sdk/packages/core/src/messages/
execution.ts`.

**`from_wire` / `to_wire` are explicit on envelope models.** They do
**not** rely on pydantic's native `model_dump()` / `model_validate()`
alone, because §5.1's "unknown top-level fields MUST be ignored"
combined with §15's `x-vendor.*` round-trip rule means a v1.0 envelope
carrying `extensions["x-vendor.acme.foo"]` must come out the other side
of `from_wire(d).to_wire()` byte-equivalent in that field. pydantic v2
with `extra="allow"` preserves unknown keys on `model_dump()`, so
`to_wire(self)` is `self.model_dump(mode="json", exclude_none=True)`
— but the `extensions` field is opaque (`dict[str, Any]`) and is **not**
validated key-by-key; it is the responsibility of `_extensions.py`
(salvaged) to classify `x-vendor.*` vs `arcpx.*` vs reserved. This is
the precise seam that decides whether `extensions["x-vendor.*"]`
round-trips correctly — and the answer is: pydantic preserves the dict;
we never narrow its value type.

**`from __future__ import annotations` is ON globally.** Forward refs
between `_messages/session.py` and `_messages/execution.py` (e.g.
`SessionWelcomePayload.capabilities.agents` references the
`AgentInventoryEntry` type also used by `_runtime/server.py`) require
either string annotations or `TYPE_CHECKING` guards. PEP 563 deferred
evaluation gives the former for free, and pydantic v2 supports it
natively (it re-evaluates annotations at model-build time via
`get_type_hints`). The cost — `inspect.signature(...)` returns strings,
which breaks naïve `click` option parsing in `cli.py` — is mitigated by
Click's explicit `type=` argument; no project file relies on runtime
annotation introspection.

**No `attrs`, no `msgspec`, no `dataclasses`** for wire types. Mixing
type-model libraries fractures the validator-pipeline: every cross-
module function call would need to pick which framework's parse rules
apply. One choice, applied everywhere wire-bound types live.

## 4. Error hierarchy

Single root, fifteen concrete leaves matching spec §12 exactly. The TS
reference at `typescript-sdk/packages/core/src/errors.ts:ERROR_CODES`
enumerates the same fifteen. Each class fixes its `code: ClassVar[str]`
and `default_retryable: ClassVar[bool]` at class scope so the registry
helper can construct from a `code` string without per-class
`if/elif` branches.

```
ARCPError(Exception)
├── PermissionDeniedError              code="PERMISSION_DENIED",           retryable=False
├── LeaseSubsetViolationError          code="LEASE_SUBSET_VIOLATION",      retryable=False
├── JobNotFoundError                   code="JOB_NOT_FOUND",               retryable=False
├── DuplicateKeyError                  code="DUPLICATE_KEY",               retryable=False
├── AgentNotAvailableError             code="AGENT_NOT_AVAILABLE",         retryable=False
├── AgentVersionNotAvailableError      code="AGENT_VERSION_NOT_AVAILABLE", retryable=False   (v1.1 §12)
├── CancelledError                     code="CANCELLED",                   retryable=False
├── TimeoutError                       code="TIMEOUT",                     retryable=False
├── ResumeWindowExpiredError           code="RESUME_WINDOW_EXPIRED",       retryable=False
├── HeartbeatLostError                 code="HEARTBEAT_LOST",              retryable=False
├── LeaseExpiredError                  code="LEASE_EXPIRED",               retryable=False   (v1.1 §12, §9.5)
├── BudgetExhaustedError               code="BUDGET_EXHAUSTED",            retryable=False   (v1.1 §12, §9.6)
├── InvalidRequestError                code="INVALID_REQUEST",             retryable=False
├── UnauthenticatedError               code="UNAUTHENTICATED",             retryable=False
└── InternalError                      code="INTERNAL_ERROR",              retryable=True    (only retryable code per §12)
```

`retryable` defaults are exactly as spec §12 dictates: "`LEASE_EXPIRED`
and `BUDGET_EXHAUSTED` MUST be returned with `retryable: false`",
"`INTERNAL_ERROR`. Always retryable." For the audit's note on the
existing 20-code gRPC enum
([`02-current-audit.md` §1 row "Error taxonomy"](./02-current-audit.md)),
the only salvageable mappings are deliberate: `INVALID_ARGUMENT →
INVALID_REQUEST`, `DEADLINE_EXCEEDED → TIMEOUT`, `NOT_FOUND →
JOB_NOT_FOUND` (job-scoped only). Everything else in the old enum is
deleted — no `UNAVAILABLE`, `DATA_LOSS`, `ABORTED`, `OUT_OF_RANGE`,
`UNIMPLEMENTED`, `RESOURCE_EXHAUSTED`, `FAILED_PRECONDITION`,
`BACKPRESSURE_OVERFLOW`, `LEASE_REVOKED`.

```python
# _errors.py — registry helper, type-safe.
_BY_CODE: dict[str, type[ARCPError]] = {
    cls.code: cls
    for cls in (
        PermissionDeniedError, LeaseSubsetViolationError, JobNotFoundError,
        DuplicateKeyError, AgentNotAvailableError, AgentVersionNotAvailableError,
        CancelledError, TimeoutError, ResumeWindowExpiredError, HeartbeatLostError,
        LeaseExpiredError, BudgetExhaustedError, InvalidRequestError,
        UnauthenticatedError, InternalError,
    )
}

def error_from_wire(payload: ErrorPayload) -> ARCPError: ...
    # Looks up cls = _BY_CODE.get(payload.code, InternalError) — unknown codes
    # collapse to InternalError per spec §12 catch-all + retryable=True default.
```

Mirrors TS `typescript-sdk/packages/core/src/errors.ts:errorFromPayload`.

## 5. Public API sketch

Signatures only. `Self` from `typing` is used for fluent returns.
`Awaitable[X]` for promised returns. `AsyncIterator[X]` for streaming.
PEP 585 / `typing.Generic[T]` for generics (PEP 695 syntax deferred
until Phase 3 confirms Python ≥3.12). All public types use snake_case
methods.

### 5.1 `ARCPClient` (in `arcp._client.client`, re-exported as `arcp.client.ARCPClient`)

```python
class ARCPClient:
    def __init__(
        self,
        *,
        client: ClientInfo,
        auth_scheme: AuthScheme,
        token: str,
        capabilities: Capabilities | None = None,
        features: tuple[str, ...] | None = None,            # default = V1_1_FEATURES
        auto_ack: AutoAckOptions | bool = False,
        handshake_timeout_sec: float = 5.0,
        logger: Logger | None = None,
    ) -> None: ...

    async def connect(self, transport: Transport) -> SessionWelcomePayload: ...
    async def resume(self, transport: Transport, resume: SessionResume) -> SessionWelcomePayload: ...

    @property
    def negotiated_features(self) -> tuple[str, ...]: ...
    def has_feature(self, name: str) -> bool: ...

    async def submit(
        self,
        *,
        agent: str,                                          # "name" or "name@version" (§7.5)
        input: Any,
        lease_request: Lease | None = None,
        lease_constraints: LeaseConstraints | None = None,    # §9.5
        idempotency_key: str | None = None,
        max_runtime_sec: int | None = None,
        trace_id: TraceId | None = None,
    ) -> JobHandle: ...

    async def cancel_job(self, job_id: JobId, *, reason: str | None = None) -> None: ...

    async def list_jobs(
        self,
        *,
        filter: ListJobsFilter | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> SessionJobsPayload: ...                              # §6.6

    async def subscribe(
        self,
        job_id: JobId,
        *,
        history: bool = False,
        from_event_seq: int | None = None,
    ) -> JobSubscription: ...                                 # §7.6

    async def ack(self, last_processed_seq: int) -> None: ... # §6.5

    async def close(self, *, reason: str | None = None) -> None: ...

    # Async-iterator event surface — preferred over a callback registry because
    # asyncio idiom is `async for`. Internally fed by the read pump; cancel-safe.
    def events(self) -> AsyncIterator[Envelope]: ...
```

`JobHandle` (in `arcp._client.handles`):

```python
class JobHandle:
    job_id: JobId
    agent_ref: str                                       # resolved "name@version"
    lease: Lease
    lease_constraints: LeaseConstraints | None
    budget: dict[str, float] | None
    trace_id: TraceId | None

    @property
    async def done(self) -> JobResultPayload: ...        # awaitable
    def events(self) -> AsyncIterator[JobEventPayload]: ...
    def chunks(self) -> AsyncIterator[ResultChunkBody]: ... # §8.4 reader
    async def collect_chunks(self) -> bytes | str: ...   # mirrors TS collectChunks
```

`done` is an **awaitable property**, not a method — `await handle.done`.
Implementation: `__await__` on a small awaitable wrapper holding the
`asyncio.Future[JobResultPayload]`. Mirrors TS `handle.done`. `events()`
and `chunks()` are async iterators, **not** awaitables; the user picks
between `await handle.done` (terminal) and `async for ev in
handle.events()` (streaming). Both surfaces coexist — `events()` is a
buffered fan-out of the same underlying queue the awaitable drains.

### 5.2 `ARCPRuntime` (in `arcp._runtime.server`, re-exported as `arcp.runtime.ARCPRuntime`)

```python
class ARCPRuntime:
    def __init__(
        self,
        *,
        runtime: RuntimeInfo,
        capabilities: Capabilities,
        bearer: BearerVerifier,
        heartbeat_interval_sec: int = 30,
        resume_window_sec: int = 600,
        cancel_grace_ms: int = 30_000,
        idempotency_ttl_ms: int = 24 * 60 * 60 * 1000,
        max_buffered_events: int = 10_000,
        max_buffered_bytes: int = 16 * 1024 * 1024,
        max_concurrent_jobs: int = 100,
        back_pressure_threshold: int = 1000,
        job_authorization_policy: JobAuthorizationPolicy | None = None,
        event_log: EventLog | None = None,
        logger: Logger | None = None,
    ) -> None: ...

    def register_agent(self, name: str, fn: Agent) -> Self: ...                              # §7.1
    def register_agent_version(self, name: str, version: str, fn: Agent) -> Self: ...         # §7.5
    def set_default_agent_version(self, name: str, version: str) -> Self: ...                # §7.5

    async def accept(self, transport: Transport) -> None: ...     # blocks until session ends
    async def close(self) -> None: ...
```

### 5.3 `Transport` protocol — verbatim from current `transport/base.py`

```python
# arcp._transport.base — salvage of src/arcp/transport/base.py
class Transport(Protocol):
    async def send(self, envelope: dict[str, Any]) -> None: ...
    async def recv(self) -> dict[str, Any]: ...
    async def close(self) -> None: ...
    @property
    def is_closed(self) -> bool: ...

class TransportClosed(Exception): ...
```

The wire-side interface stays a dict, not an `Envelope` model, because
the read pump validates **after** receiving raw bytes (the round-trip
schema is in `_envelope.py`). This also matches TS
`typescript-sdk/packages/core/src/transport/memory.ts` where
`SendableFrame = unknown` is the boundary type.

### 5.4 `Agent` — the registered function shape

```python
# arcp._runtime.job — public alias re-exported as arcp.runtime.Agent
Agent = Callable[[Input, JobContext], Awaitable[Output | None]]

@dataclass(frozen=True, slots=True)
class JobContext:
    job_id: JobId
    session_id: SessionId
    agent: str                              # bare name
    agent_version: str | None
    agent_ref: str                          # "name@version" or bare name
    lease: Lease
    lease_constraints: LeaseConstraints | None
    budget: Mapping[str, float]             # read-only view of remaining counters
    trace_id: TraceId | None
    signal: asyncio.Event                   # set() on cancel, before CancelledError
    logger: Logger

    async def log(self, level: LogLevel, message: str, attributes: dict[str, Any] | None = None) -> None: ...
    async def thought(self, text: str) -> None: ...
    async def status(self, phase: str, message: str | None = None) -> None: ...
    async def metric(self, body: MetricBody) -> None: ...
    async def tool_call(self, body: ToolCallBody) -> None: ...
    async def tool_result(self, body: ToolResultBody) -> None: ...
    async def progress(self, current: int, *, total: int | None = None, units: str | None = None, message: str | None = None) -> None: ...        # §8.2.1
    async def result_chunk(self, body: ResultChunkBody) -> None: ...                              # §8.4 raw
    def stream_result(self, *, result_id: str | None = None) -> ResultStream: ...                  # §8.4 writer
    async def delegate(self, *, agent: str, input: Any, lease_request: Lease, lease_constraints: LeaseConstraints | None = None) -> DelegateAck: ... # §10

class ResultStream(Protocol):
    async def write(self, data: bytes | str, *, encoding: Literal["utf8", "base64"] | None = None) -> None: ...
    async def close(self, *, summary: str | None = None) -> None: ...  # finalizes job.result

    # ResultStream is an async context manager so `async with ctx.stream_result() as
    # stream:` is the canonical idiom. __aexit__ on the exception path calls
    # close() with `more=False` on the in-flight chunk so a half-streamed result
    # never leaves the wire dangling; see 06-examples.md §4 for the demonstrated
    # idiom and 07-tests.md §2.3 for the regression test.
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None: ...
```

`signal` is an `asyncio.Event` even though §2 above commits to
`CancelledError` as the primary cancel mechanism — both are exposed,
and the `Event` is **always** set before the `CancelledError` is
raised. Agent authors who prefer a polling style write `while not
ctx.signal.is_set(): ...`; agent authors who prefer structured
concurrency write nothing and let `CancelledError` unwind.

### 5.5 `SessionContext` (server-side, in `arcp._runtime.session`)

```python
class SessionContext:
    state: SessionState                                  # session id, principal, resume token
    jobs: JobManager
    pending: PendingRegistry
    logger: Logger

    @property
    def negotiated_features(self) -> tuple[str, ...]: ...
    def has_feature(self, name: str) -> bool: ...

    def record_ack(self, last_processed_seq: int) -> None: ...   # §6.5
    def next_event_seq(self) -> int: ...                          # §8.3 — non-await primitive

    async def send(self, envelope: Envelope) -> None: ...         # routes to write pump + subscriber fan-out

    @property
    def latest_event_seq(self) -> int: ...
    def set_event_seq(self, value: int) -> None: ...              # used during resume replay
```

### 5.6 `Job` (server-side, in `arcp._runtime.job`)

```python
class Job:
    job_id: JobId
    session_id: SessionId
    agent: str
    agent_version: str | None
    lease: Lease
    lease_constraints: LeaseConstraints | None
    budget: dict[str, float]                  # mutable per-currency counters
    initial_budget: dict[str, float]
    parent_job_id: JobId | None
    delegate_id: str | None
    trace_id: TraceId | None
    submitter_principal: str | None
    state: JobStateName
    chunked_result_started: bool

    @property
    def agent_ref(self) -> str: ...

    def apply_cost_metric(self, name: str, value: float, unit: str | None) -> float | None: ...   # §9.6
    def should_emit_budget_remaining(self, currency: str) -> bool: ...                             # debounce

    async def emit_accepted(self) -> None: ...
    async def emit_event_kind(self, kind: str, body: Any) -> None: ...
    async def emit_result(self, result: JobResultPayload) -> None: ...   # §8.4 mix check
    async def emit_error(self, payload: ErrorPayload) -> None: ...
```

`emit_*` all funnel through `SessionContext._stamp_and_emit` (the
single non-await primitive from §2).

## 6. Idiomatic hard rules

- **`__init__.py` re-export floor.** Only `arcp/__init__.py`,
  `arcp/client/__init__.py`, `arcp/runtime/__init__.py`, and
  `arcp/middleware/__init__.py` may contain re-exports. Every `_*`
  package's `__init__.py` is **empty except** for `__all__ = ()` and a
  one-line docstring. Verify with
  `grep -rn "^from " src/arcp/_*/__init__.py` returning **nothing**.

  The four enumerated public surfaces:

  ```
  arcp                        ARCPError + 14 subclasses, ErrorCode,
                              PROTOCOL_VERSION, IMPL_VERSION, V1_1_FEATURES,
                              Envelope (frozen, read-only), Lease,
                              LeaseConstraints, Transport, TransportClosed,
                              MemoryTransport, pair_memory_transports,
                              StdioTransport, WebSocketTransport
  arcp.client                 ARCPClient, JobHandle, JobSubscription,
                              AutoAckOptions, SessionWelcomePayload,
                              SessionJobsPayload, ListJobsFilter, SessionResume
  arcp.runtime                ARCPRuntime, JobContext, Agent,
                              BearerVerifier, StaticBearerVerifier,
                              JWTVerifier, JobAuthorizationPolicy,
                              EventLog, ResultStream
  arcp.middleware             asgi.arcp_asgi_app,
                              aiohttp.arcp_aiohttp_handler,
                              aiohttp.serve_arcp_aiohttp,
                              otel.with_tracing
  ```

- **No module-level mutable globals.** Registries (agents, error codes,
  message types) live on instance state (`ARCPRuntime._agents`,
  `_BY_CODE` is a module-level frozen `dict` populated by class
  enumeration only, the `_messages` registry is built at import time
  and frozen). Verify with `grep -rn "^[A-Z_]\+ = []\|^[A-Z_]\+ = {}"
  src/arcp/` returning only the frozen literals.

- **No metaclasses.** The pydantic v2 `ModelMetaclass` is the only
  metaclass in scope, and it arrives via inheritance from `BaseModel`
  — not authored here. Anything else (e.g., auto-registering Error
  subclasses via `__init_subclass__`) is **declined**: the
  `_BY_CODE` dict is one-line enumeration, three lines of metaclass
  magic would replace zero lines of duplication. Cost > benefit.

- **`__all__` on every public module.** `arcp/__init__.py`,
  `arcp/client/__init__.py`, `arcp/runtime/__init__.py`,
  `arcp/middleware/__init__.py`, and every public-but-flat module
  (`_envelope.py`, `_errors.py`, `_version.py`, the `_transport/*`
  salvaged modules). pyright strict mode flags non-`__all__`-exported
  attributes accessed externally; this keeps the public surface a
  single grep target.

- **One-line module docstrings.** Per the docstring example already
  present in `src/arcp/transport/base.py` (the audit's "Salvage"
  baseline). The TS reference uses two-line module headers (`// ARCP
  v1.1 (additive over v1.0) runtime.` …); the Python equivalent is a
  single triple-quoted line. Multi-paragraph rationale lives in this
  planning tree, not in source.

- **No `if TYPE_CHECKING:` re-imports for public types.** `JobContext`,
  `Envelope`, `Lease`, `Transport`, `ARCPError`, `JobHandle` all live
  on the public surface and must be available at runtime — agent
  authors call `isinstance(err, ARCPError)`, runtime authors annotate
  `def handler(ctx: JobContext) -> ...`. `TYPE_CHECKING` is permitted
  only for **internal** cycle breakage (e.g., `_runtime/server.py` ↔
  `_runtime/job.py` for back-references on `Job.owning_session`).
  Verify with `grep -rn "TYPE_CHECKING" src/arcp/` and confirm every
  hit is on a `_*` module, never under `arcp/{client,runtime,
  middleware}/__init__.py`.

---

Cross-references for downstream phases:

- **Phase 5 (middleware)** owns the bodies of `arcp/middleware/{asgi,
  aiohttp,otel}.py`. Their import paths and exported names are fixed
  here.
- **Phase 6 (examples)** populates the repo-root `examples/` directory
  (not a subpackage of `arcp`) mirroring `typescript-sdk/examples/`
  (21 directories per [`06-examples.md` §1](./06-examples.md): 9 v1.0
  core + 9 v1.1 features + 3 host integrations).
- **Phase 7 (tests)** owns the property test of the `_stamp_and_emit`
  invariant in §2, the round-trip property of `from_wire` /
  `to_wire` in §3, and the registry coverage of `error_from_wire` in
  §4 (all 15 codes round-trip; unknown codes collapse to
  `InternalError`).
- **Phase 9 (diagrams)** owns the TaskGroup containment tree from §2
  (session-level TaskGroup, job-level inner TaskGroup, the
  out-of-TaskGroup heartbeat task and its Future signal).
- **Phase 10 (synthesis)** must restate this document's pydantic-v2 /
  asyncio / Python ≥3.11 commitments alongside Phase 3's library
  picks; any disagreement is reconciled in Phase 10.
