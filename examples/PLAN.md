# Examples Plan

Eleven illustrative ARCP-native Python codebases under
`python-sdk/examples/`. Each example imports from the in-repo `arcp`
package (`ARCPClient`, `ARCPRuntime`, `Envelope`, `ErrorCode`, payload
models from `arcp.messages.*`) as if it were a published `arcp>=1.0,<2.0`
SDK. Examples are illustrative excerpts, not runnable end-to-end.

Conventions across all eleven:

- Python 3.12+, fully type-annotated, ruff-clean at line length 80.
- `config.py` owns all env loading, endpoints, lease defaults,
  capability declarations, model IDs, framework configs. No
  `os.environ` or magic constants outside `config.py`.
- 200–400 LOC across 3–7 modules, plus `requirements.txt` (pinned)
  and `README.md`.
- Envelope field names, message types, and error codes match RFC-0001
  v2 exactly. Custom message types follow §21.1
  `arcpx.<domain>.<name>.v<n>` naming.
- Production tone — realistic names, plausible surrounding business
  logic, occasional `# TODO:` / `# NOTE:` where a real engineer would
  leave them. No tutorial voice, no defensive framework wrapping.

Top-level `examples/README.md` indexes the eleven, plus a banner that
the code is illustrative against the in-repo `arcp` SDK and not meant
to run end-to-end.

---

## 1. `leases/` — Sandboxed system-ops agent

**Scenario.** An on-call agent diagnoses a Linux host: reads logs,
inspects systemd units, and occasionally restarts a service. Every
side-effecting shell command is gated by a time-boxed lease scoped to
a single binary + argv prefix. Read-only commands run under a broad
read lease; mutating commands trigger a `permission.request`.

**ARCP primitives.** Sessions & auth (§8), permission challenge flow
(§15.4), lease lifecycle (§15.5), trust elevation
(`trust.elevate.privileged`, §15.6), structured logs and metrics
(§17.2/§17.3), error taxonomy (`PERMISSION_DENIED`, `LEASE_EXPIRED`,
§18.2), `kind: thought` reasoning stream (§11.4).

**Framework.** Plain `anthropic` SDK — the agent surface is thin and
the interesting code is the lease plumbing.

**Files.**
- `main.py` — wires runtime client, agent loop, sandbox executor.
- `config.py` — ARCP endpoint, bearer token, lease horizons, allowed
  binary prefixes, model id.
- `agent.py` — Anthropic tool-use loop emitting `kind: thought`.
- `leases.py` — request/refresh/revoke helpers, scoped lease cache.
- `sandbox.py` — subprocess executor that demands a valid lease per
  call.
- `prompts.py` — short system prompt, audit footer.

**Libraries.** `arcp`, `anthropic`, `pydantic`, `structlog`.

---

## 2. `delegation/` — Fan-out via `agent.delegate`

**Scenario.** A research orchestrator dispatches three independent
delegation (web-search, code-search, doc-search) over `agent.delegate`,
each running on a peer runtime. Partial results stream back; one
subagent fails with a retryable error and its envelope is surfaced
without poisoning the others. Final synthesis runs locally.

**ARCP primitives.** `agent.delegate` (§14), shared `trace_id`
propagation (§17.1), per-job error envelopes (§18), stream
multiplexing across `stream_id`s (§11), partial-failure tolerance,
`job.completed`/`job.failed` terminal events (§10.2).

**Framework.** LangGraph — graph nodes map cleanly to delegated jobs
with checkpointed merge state.

**Files.**
- `main.py` — graph construction, run, final aggregation.
- `config.py` — peer runtime URLs, model ids, fan-out budget,
  per-subagent timeouts.
- `graph.py` — LangGraph nodes for fan-out, gather, synthesize.
- `delegation.py` — wraps `agent.delegate` envelopes, tracks per-peer
  jobs.
- `aggregator.py` — async iterator that merges streams keyed by
  `trace_id`.
- `synthesis.py` — terminal LLM call producing final answer.

**Libraries.** `arcp`, `langgraph`, `langchain-core`, `pydantic`,
`structlog`, `anyio`.

---

## 3. `permission_challenge/` — Reviewer holds veto via permission

**Scenario.** Two-agent loop: a generator proposes a patch, a reviewer
inspects it. The final `apply_patch` step is gated by a
`permission.request("repo.write")` that the reviewer answers with
either `permission.grant` or `permission.deny`. On deny, the reviewer
returns a structured error and a `kind: thought` revision rationale;
the generator iterates up to N times before giving up.

**ARCP primitives.** Permission challenge flow (§15.4), structured
errors with `cause` chaining (§18.1), `kind: thought` stream (§11.4),
bounded retry with `idempotency_key` per attempt (§6.4),
`FAILED_PRECONDITION` / `PERMISSION_DENIED` codes (§18.2).

**Framework.** AutoGen — two-agent conversation matches the pattern.

**Files.**
- `main.py` — wires agents, runs the bounded review loop.
- `config.py` — runtime endpoint, max revisions, model ids.
- `agents.py` — `GeneratorAgent`, `ReviewerAgent` definitions.
- `review_gate.py` — emits `permission.request`, awaits decision.
- `patches.py` — patch model + idempotency key derivation.
- `prompts.py` — generator and reviewer system prompts.

**Libraries.** `arcp`, `pyautogen`, `pydantic`, `structlog`,
`unidiff`.

---

## 4. `extensions/` — Custom extension namespace for SDR

**Scenario.** A reference for §21. Defines `arcpx.sdr.tune.v1`,
`arcpx.sdr.capture.v1`, `arcpx.sdr.demodulate.v1`,
`arcpx.sdr.gain.v1`, advertises them in `capabilities.extensions`,
and demonstrates correct unknown-message handling (`UNIMPLEMENTED`
nack vs silent drop on `extensions.optional: true`). The example
flow: tune to 145.500 MHz (2m ham FM calling), capture 5 s of IQ at
2.048 MS/s, decimate, NBFM-demodulate, write to disk as an artifact
ref. Hardware access goes through `SoapySDR`.

**ARCP primitives.** Extension naming (§21.1), capability negotiation
of extensions (§21.2), unknown-message handling (§21.3), artifacts
(§16) for IQ buffers, metrics (`bytes.in`, custom
`arcpx.sdr.samples_dropped`).

**Framework.** None — domain-specific. ARCP plumbing + SoapySDR
bindings is the point.

**Files.**
- `main.py` — capture-then-demodulate scenario.
- `config.py` — device args, default freq/sample-rate/gain, PPM,
  artifact retention.
- `extensions.py` — Pydantic payload models for the four extension
  types, registration helper.
- `radio.py` — SoapySDR wrapper exposing `tune`, `capture`,
  `set_gain`.
- `dsp.py` — decimation and NBFM demodulation.
- `runtime_handlers.py` — runtime-side dispatch for the extension
  message types, including the optional-vs-required nack logic.

**Libraries.** `arcp`, `soapysdr` (referenced as published binding
even where not pip-installable on every host), `numpy`, `scipy`,
`pydantic`, `structlog`.

**Spec ambiguity to flag.** §21.3 says receivers MUST nack unknown
messages unless `extensions.optional: true`, but the envelope schema
lists `extensions` as a free-form object — the optional-flag
convention is implied, not specified. I'll surface this in
`LEARNED.md`.

---

## 5. `handoff/` — Cheap-first, escalate via `agent.handoff`

**Scenario.** A local Haiku-class runtime tries the request first.
If its self-reported confidence drops below a threshold or the user
asks for "deep mode", it issues `agent.handoff` to a remote Opus
runtime, preserving `session_id`-equivalent context via shared
`trace_id` and a handoff artifact carrying the conversation so far.

**ARCP primitives.** Capability negotiation (§7) — handoff target
chosen by advertised capabilities, `agent.handoff` (§14), runtime
identity verification (§8.3), artifacts for context transfer (§16),
tracing (§17.1).

**Framework.** Plain `anthropic` SDK, but with LiteLLM also imported
for the cheap-tier provider routing.

**Files.**
- `main.py` — request entry, tier selection, handoff orchestration.
- `config.py` — endpoints for both runtimes, threshold, runtime
  fingerprints, model ids.
- `tiers.py` — tier definitions (capabilities, cost weights).
- `handoff.py` — builds `agent.handoff` envelope, packages context
  artifact.
- `confidence.py` — heuristic + self-report confidence aggregator.

**Libraries.** `arcp`, `anthropic`, `litellm`, `pydantic`,
`structlog`.

---

## 6. `lease_revocation/` — Per-table, per-op leases

**Scenario.** A DB admin agent answers ops questions against a
Postgres warehouse. Read leases (`db.read` scoped to schema/table)
are pre-granted at session open. Any `INSERT`/`UPDATE`/`DELETE`/DDL
triggers `permission.request` with `resource: "table:public.orders"`
and `operation: "write"`. Granted leases live for 5 min, refreshable
once. Revoked mid-query, the executor surfaces `LEASE_REVOKED`.

**ARCP primitives.** Lease lifecycle full path (§15.5):
request → grant → use → refresh → revoke. Permission challenge
(§15.4), `LEASE_EXPIRED`/`LEASE_REVOKED`/`PERMISSION_DENIED` codes
(§18.2), typed contracts via Pydantic AI for tool boundaries.

**Framework.** Pydantic AI — typed tools at the SQL boundary make
the lease check feel like part of the type contract.

**Files.**
- `main.py` — entry, agent run.
- `config.py` — DSN, lease horizons, mutating-statement matchers.
- `agent.py` — Pydantic AI `Agent` with `run_sql` tool.
- `lease_guard.py` — parses SQL, classifies op, requests lease if
  needed.
- `sql_classifier.py` — uses `sqlglot` to identify mutating ops and
  affected tables.
- `runtime_policy.py` — sample runtime-side policy showing how the
  grant decision is made.

**Libraries.** `arcp`, `pydantic-ai`, `sqlglot`, `asyncpg`,
`structlog`.

---

## 7. `subscriptions/` — Three Observers, one session

**Scenario.** A primary agent runs a routine ingestion. Three Observer
clients hold subscriptions: (1) a structlog stdout sink, (2) a SQLite
replay store using the SDK's `arcp.store.eventlog` schema, (3) an
OTLP exporter pushing tracing/metrics to a collector. Filters scope
each observer differently (logs subscribe to all; SQLite filters out
`kind: thought`; OTLP only on `metric` and `trace.span`). No observer
ever issues a command.

**ARCP primitives.** Subscriptions (§13), filtering (§13.2),
backfill via `since.after_message_id` (§13.3), Observer role
(§Architecture §5), tracing/metrics interop (§17), backpressure
shedding (§13.4 / §6.5).

**Framework.** OpenTelemetry SDK + structlog. No agent framework —
just the three sinks.

**Files.**
- `main.py` — boots the producing agent + three observers.
- `config.py` — subscription filters, OTLP endpoint, SQLite path.
- `producer.py` — minimal agent producing varied event traffic.
- `sinks/stdout_sink.py` — structlog formatter.
- `sinks/sqlite_sink.py` — uses `aiosqlite` and the SDK schema.
- `sinks/otlp_sink.py` — OTLP exporter for spans + metrics.
- `subscriptions.py` — typed wrappers around `subscribe` envelopes.

**Libraries.** `arcp`, `structlog`, `aiosqlite`,
`opentelemetry-sdk`, `opentelemetry-exporter-otlp`, `pydantic`.

---

## 8. `heartbeats/` — Dynamic peer-runtime federation

**Scenario.** A supervisor runtime hosts a shared task queue.
Worker peer runtimes register with capability manifests, take work
via `agent.delegate`, send heartbeats, and deregister cleanly. On
two consecutive missed heartbeats the supervisor reroutes the
in-flight job to another worker (using its `idempotency_key` to
guarantee single execution).

**ARCP primitives.** `agent.delegate` (§14), heartbeats (§10.3) and
`HEARTBEAT_LOST` recovery, `idempotency_key` for safe re-dispatch
(§6.4), capability advertisement (§7), session lifecycle on
worker-runtimes (§9), trust levels (§15.3).

**Framework.** CrewAI — crew/agent roles map naturally to peer
runtimes; the supervisor is a Crew with dynamic membership.

**Files.**
- `main.py` — boots supervisor, simulates worker registration.
- `config.py` — supervisor endpoint, heartbeat interval, recovery
  policy, job retention.
- `supervisor.py` — roster, dispatch, reroute on heartbeat loss.
- `worker.py` — registers, executes delegated jobs, emits
  heartbeats.
- `roster.py` — capability index for routing.
- `crew.py` — CrewAI definitions for the worker roles.

**Libraries.** `arcp`, `crewai`, `pydantic`, `structlog`, `anyio`.

---

## 9. `capability_negotiation/` — Capability-driven routing

**Scenario.** A LiteLLM-style router fronts several model-serving
peer runtimes. Each runtime advertises capabilities including
`arcpx.market.cost_per_mtok.v1` and `arcpx.market.p50_latency_ms.v1`.
The router selects based on per-request constraints and falls back
through an ordered handoff chain on `UNAVAILABLE`/`RESOURCE_EXHAUSTED`.
Cost is aggregated via the standard `cost.usd` metric (§17.3.1).

**ARCP primitives.** Capability negotiation (§7), extension fields
on capabilities (§21), `agent.handoff` chains (§14), standardized
metrics (`tokens.used`, `cost.usd`, `latency.ms`, §17.3.1), retry
classification per error taxonomy (§18.3).

**Framework.** LiteLLM as the underlying provider abstraction;
ARCP as the runtime substrate sitting above it.

**Files.**
- `main.py` — request entry, route, fall back, return.
- `config.py` — peer endpoints, fallback chains, constraint
  defaults, model map.
- `router.py` — selection algorithm (cost vs latency vs class).
- `fallback.py` — ordered handoff with retry classifier.
- `metering.py` — collects `tokens.used` / `cost.usd` from the
  envelope stream into per-tenant counters.
- `extensions.py` — declares the marketplace extension fields.

**Libraries.** `arcp`, `litellm`, `pydantic`, `structlog`,
`tenacity`.

---

## 10. `resumability/` — Checkpointed, resumable research job

**Scenario.** A multi-step research job (plan → gather → synthesize
→ critique → finalize) takes ~30 min. Each step emits
`job.checkpoint`. The process is killed mid-synthesis. A resume
client reconnects with `resume` carrying `after_message_id` and
`checkpoint_id`; the runtime replays the canonical event stream and
the job continues from the synthesis step. Step idempotency is
guaranteed by per-step `idempotency_key`.

**ARCP primitives.** Resumability (§19), checkpoints (§10),
`idempotency_key` semantics (§6.4), durable session reconnect (§9),
`DATA_LOSS` handling on retention expiry (§19), heartbeats during
long steps (§10.3).

**Framework.** LangGraph (checkpointed graph state per step) with
LlamaIndex doing the document gathering.

**Files.**
- `main.py` — start/resume entry points.
- `config.py` — runtime endpoint, checkpoint cadence, retention
  window, model ids, index paths.
- `graph.py` — five-node LangGraph with custom checkpointer that
  emits `job.checkpoint`.
- `gather.py` — LlamaIndex retrieval step.
- `idem.py` — derives stable `idempotency_key` per (job_id, step).
- `resume.py` — reconnect logic, replay handler, gap detection.

**Libraries.** `arcp`, `langgraph`, `langchain-core`,
`llama-index-core`, `llama-index-readers-web`, `pydantic`,
`structlog`.

---

## 11. `reasoning_streams/` — Bounded reflection via stream subscription

**Scenario.** A primary agent emits its reasoning as a `kind: thought`
stream. A mirror runtime subscribes, runs a critique model, and feeds
each critique back as an `arcpx.mirror.critique.v1` event the primary
consumes between steps. Reflection is bounded by max depth (3) and a
budget tracked via the `tokens.used` metric — when the budget is
exceeded the mirror unsubscribes and the primary continues without
critique.

**ARCP primitives.** `kind: thought` reasoning streams (§11.4),
read-only subscription with type filter (§13), custom extension
event (§21), metric-driven termination (`tokens.used`, §17.3.1),
graceful `unsubscribe` (§13.4).

**Framework.** LangGraph for the primary agent; the mirror is a
bare ARCP client + Anthropic call.

**Files.**
- `main.py` — boots primary + mirror, runs sample task.
- `config.py` — runtime endpoint, max depth, token budget, model ids.
- `primary.py` — LangGraph agent emitting `stream.chunk` of
  `kind: thought`.
- `mirror.py` — subscribes, critiques, emits extension event,
  enforces budget.
- `extensions.py` — `arcpx.mirror.critique.v1` payload model.
- `budget.py` — token budget tracker reading `metric` envelopes.

**Libraries.** `arcp`, `langgraph`, `langchain-core`, `anthropic`,
`pydantic`, `structlog`.

---

## Cross-cutting notes / spec ambiguities to surface in `LEARNED.md`

- **`extensions.optional` flag (§21.3).** The optional-vs-required
  drop semantics are described prose-side but the envelope schema
  doesn't reserve the field. `extensions` and `reasoning_streams`
  both rely on the convention.
- **Backfill ordering (§13.3).** Spec says "synthetic
  `subscription.backfill_complete`" but doesn't pin the envelope
  type — I'll model it as `event.emit` with payload `{"name":
  "subscription.backfill_complete"}`.
- **Lease scoping grammar (§15.5).** `resource` and `operation` are
  free-form strings; `lease_revocation` and `leases` adopt
  similar but not identical conventions (`table:schema.name` vs
  `host:hostname`). Worth standardizing.
- **Handoff context transfer (§14).** Spec mentions
  `shared_memory_ref` in the example payload but doesn't formalize
  context transfer. `handoff` packages context as an
  artifact and references it by `artifact_id`.
- **Capability extensions (§21 vs §7).** Capability flags can be
  booleans, lists (`extensions`), or scalar values
  (`heartbeat_interval_seconds`). `capability_negotiation` puts numeric
  marketplace capabilities under namespaced keys; the spec doesn't
  forbid this but doesn't model it either.

---

## Implementation order

1. `subscriptions` — small, mechanical, validates the
   subscription/observer envelopes I'll lean on later.
2. `leases` — exercises the lease + permission flow once cleanly.
3. `lease_revocation` — second pass on leases with richer
   scoping.
4. `delegation` — first `agent.delegate` use.
5. `handoff` — first `agent.handoff` use.
6. `heartbeats` — heartbeat loss, dynamic federation.
7. `permission_challenge` — permission challenge in a tight loop.
8. `capability_negotiation` — capability-driven routing + standard
   metrics.
9. `resumability` — checkpoint/resume.
10. `reasoning_streams` — `kind: thought` streams + extension events.
11. `extensions` — extension namespace reference.

Then write `LEARNED.md` capturing the cross-cutting findings.

---

**Awaiting approval before writing code.**
