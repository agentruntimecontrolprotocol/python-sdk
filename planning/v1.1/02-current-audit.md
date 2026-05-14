# 02 — Current SDK Audit

This audit is grounded in the working tree as of the commit that contains
this file. It maps what exists in
[`python-sdk/src/arcp/`](../../../python-sdk/src/arcp/) to what the v1.1
plan needs, and **shapes the migration's scope**: the dominant fact is
that this SDK targets [`RFC-0001-v2`](../../../python-sdk/RFC-0001-v2.md)
which is the old [`spec/docs/draft-arcp-01.md`](../../../spec/docs/draft-arcp-01.md),
not [`spec/docs/draft-arcp-02.md`](../../../spec/docs/draft-arcp-02.md) (v1.0)
or [`spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md)
(v1.1). The TypeScript reference at `../typescript-sdk/` is on draft-02.1
already (see its [`CONFORMANCE.md`](../../../typescript-sdk/CONFORMANCE.md):
all v1.0 + v1.1 sections "Implemented").

## 1. Wire-level divergence (the dominant fact)

The Python SDK is not a v1.0 implementation that needs v1.1 features added.
It is a draft-01 implementation with a wire shape, lifecycle, and error
taxonomy that the v1.0/v1.1 spec explicitly replaced. The TS
`CONFORMANCE.md` rows are not achievable here by adding code; they require
rewriting the wire surface first.

| Concern              | v1.1 spec (`draft-arcp-02.1.md`)                                                                            | Current Python (`src/arcp/`)                                                                                                                                                  | Disposition                                                       |
| -------------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Envelope constant    | `arcp: "1"` (§5.1)                                                                                          | `Envelope.arcp = "1.0"` ([`envelope.py:34`](../../../python-sdk/src/arcp/envelope.py#L34))                                                                                     | Replace constant + value.                                         |
| Envelope shape       | 8 fields: `arcp`, `id`, `type`, `session_id`, `trace_id?`, `job_id?`, `event_seq?`, `payload` (§5.1)        | 17 fields incl. `timestamp`, `source`, `target`, `stream_id`, `subscription_id`, `correlation_id`, `causation_id`, `idempotency_key`, `priority`, `extensions`, `span_id`, `parent_span_id` ([`envelope.py:24-52`](../../../python-sdk/src/arcp/envelope.py#L24)) | Replace `Envelope` entirely. No salvageable fields above the 8.   |
| Sequencing           | `event_seq` REQUIRED on `job.event`/`job.result`/`job.error`; session-scoped, monotonic, gap-free (§5.1, §8.3) | No `event_seq` field; ordering implied via SQLite `rowid` only ([`store/eventlog.py`](../../../python-sdk/src/arcp/store/eventlog.py))                                          | New session-scoped counter required; wire it through the new Job state. |
| Session handshake    | `session.hello` → `session.welcome` (§6.2)                                                                  | `session.open` → `session.challenge?` → `session.authenticate?` → `session.accepted`/`session.rejected` ([`runtime/session.py`](../../../python-sdk/src/arcp/runtime/session.py), [`messages/session.py`](../../../python-sdk/src/arcp/messages/session.py)) | Replace verbs + payload shapes. The challenge-response detour is not in v1.0/v1.1. |
| Session terminate    | `session.bye { reason }` (§6.7)                                                                             | `session.close { reason, detach_jobs }` ([`messages/session.py:140`](../../../python-sdk/src/arcp/messages/session.py#L140))                                                   | Rename + drop `detach_jobs`.                                      |
| Job lifecycle wire   | One `job.event` envelope with `payload.kind ∈ {log, thought, tool_call, tool_result, status, metric, artifact_ref, delegate, progress, result_chunk}` (§8.2)  | Eight separate verbs: `job.accepted`/`job.started`/`job.progress`/`job.heartbeat`/`job.checkpoint`/`job.completed`/`job.failed`/`job.cancelled` ([`messages/execution.py`](../../../python-sdk/src/arcp/messages/execution.py)) | Replace the entire job-event surface. v1.1's `progress` kind absorbs `JobProgressPayload`; heartbeats are session-level not job-level. |
| Terminal events      | `job.result { final_status, result?, result_id?, result_size?, summary? }` or `job.error { final_status, code, message }` (§7.3) | `job.completed { result, result_ref }`, `job.failed { code, message, retryable }`, `job.cancelled { reason, code }` ([`messages/execution.py:90-114`](../../../python-sdk/src/arcp/messages/execution.py#L90)) | Replace. Single terminal verb collapses success/error/cancel/timed_out into `final_status` discriminator. |
| Leases               | Per-job, **immutable at submit**: capability namespace → glob pattern[] (§9.1)                              | Server-side mutable `Lease` objects with `grant`/`extend`/`revoke` keyed by `lease_id`, with `permission`/`resource`/`operation` triple ([`runtime/lease.py`](../../../python-sdk/src/arcp/runtime/lease.py)) | Replace. v1.0/v1.1 has no lease IDs, no extension, no revocation. |
| Streams              | Not in spec. Tool outputs flow as `tool_result` events; large finals as `result_chunk` (§8.4)               | First-class `stream.*` message family with `StreamManager`, `desired_rate_per_second` ([`runtime/stream.py`](../../../python-sdk/src/arcp/runtime/stream.py), [`messages/streaming.py`](../../../python-sdk/src/arcp/messages/streaming.py)) | Delete the stream family. Replace user-visible streaming surface with `JobContext.streamResult()` writing `result_chunk` (§8.4). |
| Error taxonomy       | 12 v1.0 codes + 3 v1.1 codes (15 total) (§12)                                                               | 20 gRPC-style codes incl. `INVALID_ARGUMENT`, `DEADLINE_EXCEEDED`, `NOT_FOUND`, `ALREADY_EXISTS`, `RESOURCE_EXHAUSTED`, `FAILED_PRECONDITION`, `ABORTED`, `OUT_OF_RANGE`, `UNIMPLEMENTED`, `INTERNAL`, `UNAVAILABLE`, `DATA_LOSS`, `LEASE_REVOKED`, `BACKPRESSURE_OVERFLOW` ([`errors.py:15-38`](../../../python-sdk/src/arcp/errors.py#L15)) | Replace `ErrorCode` enum. Map salvageable cases: `INVALID_ARGUMENT`→`INVALID_REQUEST`, `DEADLINE_EXCEEDED`→`TIMEOUT`, `NOT_FOUND`→`JOB_NOT_FOUND` (job-scoped). Delete the rest. |
| Idempotency          | `(principal, idempotency_key, ~24h)` returns same `job_id`; conflicting params ⇒ `DUPLICATE_KEY` (§7.2)     | SQLite-backed `idempotency_results` table by `(principal, idempotency_key)` ([`store/eventlog.py:157-196`](../../../python-sdk/src/arcp/store/eventlog.py#L157))               | Keep the table; rewrite its caller to v1.0 semantics (return existing `job.accepted`; raise `DUPLICATE_KEY` on conflict). |
| Resume               | `session.hello.payload.resume = { session_id, resume_token, last_event_seq }`, rotate token on welcome (§6.3) | `control.ResumePayload` (separate message), rotation not implemented ([`messages/control.py`](../../../python-sdk/src/arcp/messages/control.py), [`runtime/server.py`](../../../python-sdk/src/arcp/runtime/server.py)) | Replace. Resume is a `session.hello` shape, not its own verb. |
| Transports           | WebSocket / stdio / others (§4)                                                                             | WebSocket / stdio / in-memory ([`transport/`](../../../python-sdk/src/arcp/transport/))                                                                                       | Keep the three transports; rewrite the wire they carry. The base interface is salvageable. |

The audit takeaway: the migration is **realign-to-v1.0** + **add-v1.1**.
The first half is the larger half. Treating it as "v1.0 + a v1.1 patch" is
the only honest framing; planning that ships v1.1 features on top of the
current draft-01 wire would not produce an ARCP v1.1 SDK.

## 2. File-by-file map (`src/arcp/`)

`Disposition` column key:

- **Rewrite** — module is on the wrong protocol; replace contents.
- **Salvage** — boundary is right (transport, auth verification interface); body mostly rewritten.
- **Delete** — concept does not exist in v1.0/v1.1.
- **Augment (v1.1 only)** — module's v1.0 shape is fine after the realign; v1.1 features extend it.

| File | What it does today | v1.0 alignment | v1.1 home | Disposition |
| ---- | ------------------ | -------------- | --------- | ----------- |
| [`__init__.py`](../../../python-sdk/src/arcp/__init__.py) | Re-exports `ARCPClient`, `ARCPRuntime`, `Envelope`, `ARCPError`, `ErrorCode`, `IMPL_VERSION`, `PROTOCOL_VERSION` | OK as a re-export pattern | Add v1.1 error classes + feature list constants | Rewrite (re-exports change with renames) |
| [`version.py`](../../../python-sdk/src/arcp/version.py) | `PROTOCOL_VERSION`/`IMPL_VERSION` constants | Wire constant must become `"1"` | Add `V1_1_FEATURES`, `intersectFeatures` helper | Rewrite |
| [`envelope.py`](../../../python-sdk/src/arcp/envelope.py) | 17-field `Envelope` with `pydantic` `extra="forbid"`, `timestamp` validator | Wrong shape (see §1 row "Envelope shape") | Field shape is invariant in v1.1 | Rewrite |
| [`errors.py`](../../../python-sdk/src/arcp/errors.py) | `ErrorCode` enum (20 gRPC-style), `ARCPError` exception, retryability map | Wrong code set | Add 3 v1.1 codes; non-retryable defaults | Rewrite |
| [`extensions.py`](../../../python-sdk/src/arcp/extensions.py) | `x-vendor.*` / `arcpx.*` extension classifier and registry | The `x-vendor.*` convention matches v1.0/§15 | No v1.1 changes | Salvage |
| [`cli.py`](../../../python-sdk/src/arcp/cli.py) | Click-based `arcp` CLI (serve, send, tail, replay) | Command set is fine; envelope construction inside is on the wrong wire | TS has parity (`pnpm tsx packages/sdk/src/cli.ts`); echo TS surface | Rewrite |
| [`auth/__init__.py`](../../../python-sdk/src/arcp/auth/__init__.py) | Package marker | — | — | Salvage |
| [`auth/bearer.py`](../../../python-sdk/src/arcp/auth/bearer.py) | Bearer-token verifier interface + static map verifier | Matches v1.0 §6.1 | No v1.1 changes | Salvage |
| [`auth/jwt.py`](../../../python-sdk/src/arcp/auth/jwt.py) | `pyjwt`-based verifier | Compatible; tied to bearer interface | No v1.1 changes | Salvage |
| [`client/__init__.py`](../../../python-sdk/src/arcp/client/__init__.py) | Re-exports `ARCPClient` | — | Surface adds `listJobs`, `subscribe`, `ack`, `negotiatedFeatures`, `hasFeature` | Rewrite |
| [`client/client.py`](../../../python-sdk/src/arcp/client/client.py) | Handshake driver, command/response correlation, event tail queue | Handshake on wrong verbs; correlation pattern survives | All v1.1 client APIs land here | Rewrite |
| [`client/handlers.py`](../../../python-sdk/src/arcp/client/handlers.py) | Inbound envelope dispatch helpers | Dispatch table tied to wrong types | Pong / progress / chunk / status handlers | Rewrite |
| [`messages/__init__.py`](../../../python-sdk/src/arcp/messages/__init__.py) | Registry: type→pydantic model | Registry pattern OK; entries wrong | Add v1.1 payloads | Rewrite |
| [`messages/session.py`](../../../python-sdk/src/arcp/messages/session.py) | `session.open`/`accepted`/`challenge`/`authenticate`/`refresh`/`evicted`/`close` payloads, `Capabilities`/`Identity` | Wrong verbs and shapes (see §1) | `session.hello`/`welcome`/`error`/`bye`/`ping`/`pong`/`ack`/`list_jobs`/`jobs` | Rewrite |
| [`messages/execution.py`](../../../python-sdk/src/arcp/messages/execution.py) | `job.accepted`/`started`/`progress`/`heartbeat`/`checkpoint`/`completed`/`failed`/`cancelled`, `tool.invoke`/`result`/`error`, `workflow.*`, `agent.delegate`/`handoff` | Wrong job lifecycle (see §1); workflow/handoff not in v1.0/v1.1 | `job.submit`/`accepted`/`event`/`result`/`error`/`cancel`/`subscribe`/`subscribed`/`unsubscribe`; `lease_constraints`/`budget`; event kinds incl. `progress`/`result_chunk` | Rewrite |
| [`messages/control.py`](../../../python-sdk/src/arcp/messages/control.py) | `ResumePayload`, `CancelPayload`/`CancelAccepted`/`CancelRefused` | Resume is `session.hello`-embedded in v1.0/v1.1; cancel is `job.cancel { reason }` (§7.4) | — | Rewrite |
| [`messages/streaming.py`](../../../python-sdk/src/arcp/messages/streaming.py) | `stream.open`/`stream.chunk`/`stream.close`/`stream.error` | Stream verbs do not exist | — | Delete |
| [`messages/subscriptions.py`](../../../python-sdk/src/arcp/messages/subscriptions.py) | Subscriber verbs (`subscribe`/`subscribe.accepted`/`subscribe.event`/`unsubscribe`/`subscribe.closed`) | Spec subscribe is **job-scoped** (`job.subscribe`/`subscribed`/`unsubscribe`) (§7.6) | Folds into `messages/execution.py` | Delete (overlapping concept), replace with v1.1 job-subscription verbs |
| [`messages/human.py`](../../../python-sdk/src/arcp/messages/human.py) | Human-in-the-loop (`human.input.request`/`human.choice.request`) | Not in v1.0/v1.1 (§1.2 Non-Goals: HITL is not in scope) | — | Delete |
| [`messages/permissions.py`](../../../python-sdk/src/arcp/messages/permissions.py) | `permission.request`/`grant`/`deny`, `lease.granted`/`refresh`/`extended`/`revoked` | Replaced by §9 lease grammar; no runtime grant/extend/revoke verbs | — | Delete |
| [`messages/artifacts.py`](../../../python-sdk/src/arcp/messages/artifacts.py) | `artifact.put`/`fetch`/`ref`/`release` | v1.0/v1.1 has only `artifact_ref` as an event-kind body, not a verb family (§8.2) | — | Delete; keep the body schema in `messages/execution.py` |
| [`messages/telemetry.py`](../../../python-sdk/src/arcp/messages/telemetry.py) | Telemetry payloads | Trace propagation is via the envelope's `trace_id` + OTel middleware (§11), not separate verbs | — | Delete |
| [`runtime/__init__.py`](../../../python-sdk/src/arcp/runtime/__init__.py) | Re-exports `ARCPRuntime` | — | — | Rewrite |
| [`runtime/server.py`](../../../python-sdk/src/arcp/runtime/server.py) | `ARCPRuntime` server: dispatch, session map, tool registry, job/stream/lease/subscription managers | Dispatch table targets wrong verbs; session map shape OK | All v1.1 handlers (`list_jobs`, `subscribe`, `ack`, `ping`) land here; `registerAgent`/`registerAgentVersion`/`setDefaultAgentVersion` APIs | Rewrite |
| [`runtime/session.py`](../../../python-sdk/src/arcp/runtime/session.py) | `SessionState` + `HandshakeDriver` (four-step handshake) | Wrong handshake state machine | Add `negotiatedFeatures`, `recordAck`, `startHeartbeat`, ack-window state | Rewrite |
| [`runtime/job.py`](../../../python-sdk/src/arcp/runtime/job.py) | `JobManager`, `JobRecord`, heartbeat timer, tool invocation, lease checks | State machine FSM is salvageable conceptually; wire is wrong | `Job.applyCostMetric`, `JobContext.progress`/`resultChunk`/`streamResult`, lease-expiry watchdog, `agent@version` resolution | Rewrite |
| [`runtime/lease.py`](../../../python-sdk/src/arcp/runtime/lease.py) | Mutable `Lease` with `grant`/`extend`/`revoke` | Wrong model entirely (see §1) | New: `validateLeaseShape`, `validateLeaseOp` (with budget + expiry), `isLeaseSubset` (incl. budget remaining), `assertLeaseConstraintsSubset`, `parseBudgetAmount`, `initialBudgetFromLease` | Rewrite |
| [`runtime/pending.py`](../../../python-sdk/src/arcp/runtime/pending.py) | `PendingRequestRegistry` (correlation-id ↔ future) | Correlation by `correlation_id` is foreign to v1.0/v1.1; replies are addressed by `id` or `request_id` (e.g. §6.6) | Salvage the pattern with `request_id` key | Salvage (rewrite key) |
| [`runtime/stream.py`](../../../python-sdk/src/arcp/runtime/stream.py) | `StreamManager` with backpressure throttle | Stream concept removed | — | Delete |
| [`runtime/subscription.py`](../../../python-sdk/src/arcp/runtime/subscription.py) | `SubscriptionManager` for the generic stream subscribe family | Concept replaced by §7.6 job-subscribe fan-out | Move job-subscriber fan-out into `runtime/server.py:SessionContext.send` (mirror TS) | Delete |
| [`runtime/artifact.py`](../../../python-sdk/src/arcp/runtime/artifact.py) | Artifact store | Spec has no artifact verbs; only `artifact_ref` event body | — | Delete |
| [`store/__init__.py`](../../../python-sdk/src/arcp/store/__init__.py) | Package marker | — | — | Salvage |
| [`store/eventlog.py`](../../../python-sdk/src/arcp/store/eventlog.py) | SQLite event log with append (dedupe), replay, idempotency table, retention GC | Append-and-replay shape matches §6.3 resume semantics; columns referencing `stream_id`/`subscription_id`/`correlation_id`/`causation_id`/`priority` are foreign | Add `event_seq` column (session-scoped INTEGER), reader by `seq > N`, ack-aware GC | Salvage (rewrite schema) |
| [`store/schema.sql`](../../../python-sdk/src/arcp/store/schema.sql) | Events table + idempotency table DDL | Schema columns wrong | New schema mirroring `event_seq`-keyed reads | Rewrite |
| [`transport/__init__.py`](../../../python-sdk/src/arcp/transport/__init__.py) | Package marker | — | — | Salvage |
| [`transport/base.py`](../../../python-sdk/src/arcp/transport/base.py) | `Transport` protocol (`send`/`recv`/`close`) + `TransportClosed` | Interface matches the TS `Transport` shape and is wire-agnostic | No v1.1 changes | Salvage |
| [`transport/in_memory.py`](../../../python-sdk/src/arcp/transport/in_memory.py) | `MemoryTransport` (queue pair) | Matches TS `MemoryTransport`; the helper for paired transports is the right test seam | No v1.1 changes | Salvage |
| [`transport/stdio.py`](../../../python-sdk/src/arcp/transport/stdio.py) | Newline-delimited JSON over stdin/stdout | Matches §4.2 | No v1.1 changes | Salvage |
| [`transport/websocket.py`](../../../python-sdk/src/arcp/transport/websocket.py) | `websockets` client + server primitive | Matches §4.1 (one transport per session); JSON text frames only | No v1.1 changes | Salvage |
| [`py.typed`](../../../python-sdk/src/arcp/py.typed) | PEP 561 marker | — | — | Salvage |

Tests (`tests/`) and examples (`examples/`) are entirely targeted at the
old wire. They are not file-by-file mapped above; their disposition is
**delete and rewrite**. Phase 6 (Examples) and Phase 7 (Tests) own the
new structure. Specific high-value coverage worth preserving — what the
old [`tests/integration/test_resume.py`](../../../python-sdk/tests/integration/test_resume.py)
and [`tests/integration/test_heartbeat.py`](../../../python-sdk/tests/integration/test_heartbeat.py)
got *right* about timing — should be lifted into the new test design as
intent, not code.

`pyproject.toml` decisions worth flagging now (Phase 3 picks finalize):

- `requires-python = ">=3.13"` ([`pyproject.toml:6`](../../../python-sdk/pyproject.toml#L6)). The bootstrap permits 3.10 minimum. 3.13 cuts off too many users for an SDK; Phase 3 should justify a downgrade to 3.11 or 3.12 (needed for `asyncio.TaskGroup` from 3.11).
- `pydantic>=2.7`, `aiosqlite`, `websockets>=13`, `structlog`, `pyjwt[crypto]`, `click`, `jsonschema` ([`pyproject.toml:9-17`](../../../python-sdk/pyproject.toml#L9)). The `jsonschema` dep is dead code if `pydantic` is the validator — Phase 3 should pick one and drop the other.
- `pyright>=1.1` is already configured strict ([`pyproject.toml:39-47`](../../../python-sdk/pyproject.toml#L39)); Phase 3 should confirm.
- `--cov-fail-under=90` ([`pyproject.toml:114`](../../../python-sdk/pyproject.toml#L114)); Phase 7 floor is 87 % — keep the stricter floor or document the relaxation.
- `aiosqlite` is the only durability dep, used solely by `eventlog.py`. Salvageable.

## 3. Gap matrix — v1.1 features against the SDK

Rows are the v1.1 surface from `01-spec-delta.md`. `state` is judged **after the
v1.0 realign** lands — i.e. assuming the v1.0 wire from §1 is in place; only
then is "partial" or "present" possible for v1.1 specifics. Without that
assumption every row is "missing" because the verbs themselves do not exist.

`target_module` is the post-realign path.

| Feature (spec §)                                                            | state   | target_module                                | risk |
| --------------------------------------------------------------------------- | ------- | -------------------------------------------- | ---- |
| `capabilities.features` array on hello + welcome (§6.2)                     | missing | `arcp/_messages/session.py`                  | L    |
| Feature intersection helper + per-session memo (§6.2)                       | missing | `arcp/_version.py`, `arcp/_runtime/session.py`, `arcp/_client/client.py` | L |
| Rich `capabilities.agents` shape (§6.2 / §7.5)                              | missing | `arcp/_messages/session.py`                  | L    |
| `session.welcome.payload.heartbeat_interval_sec` (§6.2 / §6.4)              | missing | `arcp/_messages/session.py`                  | L    |
| `session.ping` / `session.pong` (§6.4)                                      | partial — old job-level heartbeat is salvageable timing logic only | `arcp/_runtime/session.py`, `arcp/_client/client.py` | M (cancellation interaction with `TaskGroup`: pinging from a background task should not cancel the connection task) |
| `HEARTBEAT_LOST` close after 2 missed intervals (§6.4)                      | missing | `arcp/_runtime/session.py`                   | M    |
| `session.ack { last_processed_seq }` advisory flow control (§6.5)           | missing | `arcp/_runtime/session.py`, `arcp/_client/client.py` | L |
| Runtime-side ack-aware buffer release (§6.5)                                | partial — `EventLog.gc_before` exists; needs seq-based pruning | `arcp/_store/eventlog.py`, `arcp/_runtime/session.py` | M |
| Back-pressure `status` event (§6.5)                                         | missing | `arcp/_runtime/session.py`                   | L    |
| Client `autoAck` coalescing (mirror TS) (§6.5)                              | missing | `arcp/_client/client.py`                     | L    |
| `session.list_jobs` filter (`status`/`agent`/`created_after`) + cursor (§6.6) | missing | `arcp/_messages/session.py`, `arcp/_runtime/server.py` | L |
| `session.jobs` response with `request_id` echoing envelope `id` (§6.6)      | missing | `arcp/_runtime/server.py`                    | L    |
| Same-principal-only default authorization with policy hook (§6.6 / §14)     | missing | `arcp/_runtime/server.py`                    | M (this is the security default for both `list_jobs` and `subscribe` — getting it backwards leaks job existence cross-principal) |
| `job.submit.payload.agent` `name@version` grammar (§7.5)                    | missing | `arcp/_messages/execution.py`                | L    |
| Default-version resolution (§7.5)                                           | missing | `arcp/_runtime/server.py`                    | L    |
| `AGENT_VERSION_NOT_AVAILABLE` raised as `session.error` (§7.5 / §13.7)      | missing | `arcp/_runtime/server.py`, `arcp/_errors.py` | L    |
| `registerAgent`/`registerAgentVersion`/`setDefaultAgentVersion` server API (§7.5) | missing | `arcp/_runtime/server.py`              | L    |
| `job.subscribe` / `job.subscribed` / `job.unsubscribe` (§7.6)               | missing | `arcp/_messages/execution.py`, `arcp/_runtime/server.py` | M |
| History replay using subscriber-scoped `event_seq` (§7.6)                   | missing | `arcp/_runtime/server.py`                    | H — subscriber's seq counter is independent of the submitting session's; mis-wiring it would let a single fan-out event land on two subscribers with conflicting seqs and break ordering invariants the TS reference enforces in `forwardEventToSubscriber` |
| Subscriber MUST NOT have cancel authority (§7.6)                            | missing | `arcp/_runtime/server.py`                    | L    |
| `progress` event kind body schema (§8.2.1)                                  | missing | `arcp/_messages/execution.py`                | L    |
| `JobContext.progress(current, opts?)` helper                                | missing | `arcp/_runtime/job.py`                       | L    |
| `result_chunk` kind body schema (§8.4)                                      | missing | `arcp/_messages/execution.py`                | L    |
| `job.result.payload.result_id` / `result_size` (§8.4)                       | missing | `arcp/_messages/execution.py`                | L    |
| MUST NOT mix inline `result` and `result_chunk` (§8.4)                      | missing | `arcp/_runtime/job.py`                       | L    |
| `JobContext.streamResult({result_id?})` writer + `JobHandle.collectChunks()` reader | missing | `arcp/_runtime/job.py`, `arcp/_client/client.py` | M (async iterator surface — pick `async for chunk in handle.chunks()` over a callback; see `04-architecture.md`) |
| `lease_constraints.expires_at` parsing (ISO UTC, must-be-future) (§9.5)     | missing | `arcp/_messages/execution.py`, `arcp/_runtime/lease.py` | L |
| `validateLeaseOp` accepting `now` for clock injection (§9.5)                | missing | `arcp/_runtime/lease.py`                     | M (test seam — without it, lease-expiry tests rely on real time and become flaky on slow CI; mirror TS `LeaseOpContext.now`) |
| `job.error{LEASE_EXPIRED}` watchdog timer (§9.5)                            | missing | `arcp/_runtime/server.py`                    | M (lifetime: must be cancelled cleanly on terminal-event emission; cancellation interplay with `TaskGroup` is one of the H-risk items below in §4) |
| `cost.budget` amount grammar `currency:decimal` (§9.6)                      | missing | `arcp/_runtime/lease.py`                     | L    |
| Per-currency counters initialized in `job.accepted.payload.budget` (§9.6)   | missing | `arcp/_runtime/lease.py`, `arcp/_runtime/job.py` | L |
| Counter decrement on `metric{name:"cost.*"}` matching `unit` (§9.6)         | missing | `arcp/_runtime/job.py`                       | L    |
| `BUDGET_EXHAUSTED` returned via `tool_result` (preferred) or `job.error` (§9.6) | missing | `arcp/_runtime/lease.py`, `arcp/_runtime/job.py` | L |
| Runtime-emitted debounced `cost.budget.remaining` (§9.6)                    | missing | `arcp/_runtime/job.py`                       | L    |
| Subset rule: child `cost.budget` ≤ parent remaining per currency (§9.4)     | missing | `arcp/_runtime/lease.py`                     | M    |
| Subset rule: child `expires_at` ≤ parent's (§9.4)                           | missing | `arcp/_runtime/lease.py`                     | L    |
| Implicit `expires_at` inheritance when child omits constraints (§9.4)       | missing | `arcp/_runtime/server.py`                    | L    |
| OTel span attrs `arcp.lease.expires_at` / `arcp.budget.remaining` (§11)     | missing | `arcp/middleware/otel/`                      | L    |
| New error classes `BudgetExhaustedError`/`LeaseExpiredError`/`AgentVersionNotAvailableError`, all `retryable=False` (§12) | missing | `arcp/_errors.py` | L |
| Chunk-size + total-size caps with `INTERNAL_ERROR` (§14)                    | missing | `arcp/_runtime/job.py`                       | M (memory exhaustion vector if forgotten; spec note in §14 is SHOULD but the absence is observable to abusive clients) |

H-risk rationale (one sentence per row marked H above):

- **History replay seq-space**: asyncio's `TaskGroup` makes it easy to write a "broadcast to all subscribers" coroutine that increments seq inside a shared lock; the TS code uses a per-subscriber `SessionContext.nextEventSeq()` and a fan-out loop. Getting this wrong is invisible until a subscriber resumes and the replayed seqs collide with live seqs.

## 4. Specifically Python risks to call out

These are not "v1.1 features"; they are language-level seams the plan must
address explicitly because the TS reference's solutions don't transliterate.

- **Cancellation semantics**: TS abort via `AbortSignal` and Promise reject is
  not equivalent to `asyncio.CancelledError`. The lease-expiry watchdog and
  the `ctx.signal` surface (`runtime/job.py`) must agree on a single
  cancellation channel — either propagate `CancelledError` into the agent
  coroutine (preferred; preserves structured concurrency under `TaskGroup`)
  **or** expose an `asyncio.Event` and document the lack of stack unwinding
  on cancel. The TS choice (signal-driven) is **not** the Python idiom.
- **`pydantic` vs `msgspec` performance under chunked streaming**: §8.4 implies
  hot-path validation of each `result_chunk`. `pydantic` v2 is the chosen
  validator across this SDK today, but `msgspec` is faster on small fast-path
  objects. Phase 3 owns this; the v1.1 plan must commit to one before Phase 4
  designs the type model.
- **`event_seq` atomicity under concurrent jobs**: per §8.3 the counter is
  session-scoped across concurrent jobs. The TS implementation uses a single
  in-process number bump (single-threaded JS). Python's asyncio is also
  cooperative, but if any code path awaits between "compute next seq" and
  "emit", a context switch can let another emission interleave. The plan
  must require the emit primitive to be a single non-awaiting step that
  bumps the counter and dispatches in the same coroutine frame.
- **Heartbeat coupling to `TaskGroup`**: the heartbeat coroutine cannot be a
  child of the session's `TaskGroup` because a heartbeat timeout that raises
  `HeartbeatLostError` would cancel sibling tasks, including the job emit
  pump. Phase 4 must pick a non-cancellation signaling channel for this
  (probably `asyncio.Future` on the session context, set by the heartbeat
  loop and observed by the connection main loop).
- **Backpressure on `websockets` send**: the `websockets` library buffers
  writes; reaching the backpressure threshold from §6.5 requires actually
  measuring `transport.transport.get_write_buffer_size()` or analogous,
  not just timing. The lag detection in TS (`SessionContext.recordAck`
  comparing latest emitted seq to `last_processed_seq`) is the seq-based
  proxy and is what we should mirror — but the Python wrapper around
  `websockets` must not paper over send-side backpressure either.

## 5. Net scope summary (for Phase 10)

- Files to **delete**: ~10 (entire `messages/` for streaming/subscriptions/human/permissions/artifacts/telemetry; `runtime/stream.py`/`subscription.py`/`artifact.py`).
- Files to **rewrite**: ~14 (envelope, errors, version, all message payloads still in scope, all client + runtime modules except transport/auth/store schema layout).
- Files to **salvage** (interface keeps, body mostly intact): transports (4), auth (3), extensions (1), `store/eventlog.py` (schema-rewrite kind of "salvage"), `runtime/pending.py`.
- New files: middleware adapters (Phase 5), agent registry inside `runtime/server.py`, conformance harness (Phase 7), docs tree (Phase 8), diagrams (Phase 9).
- Examples: 14 old → 21 new mirroring TS `examples/README.md` (Phase 6 §1 reconciles the count after counting the TS tree directly: 22 dirs there, minus `bun/` N/A, minus `express/`+`fastify/` collapsing into one `host_asgi/`, plus a Python-native `host_aiohttp/` = 21).
- Test layers: existing ~25 test files retired; rebuilt in 4 layers per Phase 7.

This audit's main load-bearing claim — that the v1.1 plan must include
v1.0 realignment — should be re-stated in `10-synthesis.md` so the
milestones reflect it, not buried as an implementation detail of "the
v1.1 work".
