# 10 — Synthesis

This document is the reconciled rollup of `01-spec-delta.md` through
`09-diagrams.md` in [`planning/v1.1/`](./). It resolves cross-phase
contradictions, sequences the work into PR-shippable milestones,
calls out risk owners, and lists the open questions a human reviewer
must answer before milestone 1 can land.

## 1. Executive summary

**Scope.** Migrate the Python SDK to ARCP **v1.1**
([`spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md)).
The dominant fact established by [`02-current-audit.md`](02-current-audit.md):
the SDK currently targets [`RFC-0001-v2`](../../RFC-0001-v2.md) /
[`spec/docs/draft-arcp-01.md`](../../../spec/docs/draft-arcp-01.md), an
earlier draft whose wire is structurally different from v1.0/v1.1
(envelope shape, session verbs, job lifecycle, error taxonomy, lease
model all diverge). The migration is therefore **realign-to-v1.0 +
add-v1.1**, not "v1.1 on top of v1.0". Roughly two-thirds of `src/arcp/`
is rewritten; the salvageable surface is the four transports, the two
auth verifiers, the extensions classifier, the SQLite event-log
scaffolding (schema rewritten), and the pending-request correlation
pattern.

**Library picks** (from [`03-libraries.md`](03-libraries.md) §"Decisions
at a glance"):

- Runtime: `pydantic` v2 (≥ 2.9), `websockets` (≥ 13), `aiosqlite` (≥ 0.20),
  `structlog` (≥ 24), `python-ulid` (≥ 2), `opentelemetry-api` (≥ 1.27, API-only),
  `pyjwt[crypto]` (≥ 2.9), `click` (≥ 8.1), stdlib `asyncio` only.
- Conditional runtime: `httpx` (≥ 0.27) under `[project.optional-dependencies] jwks` —
  JWKS fetches only.
- Dev: `pytest` (≥ 8) + `pytest-asyncio` (≥ 0.24) + `hypothesis` (≥ 6.112) +
  `pytest-cov` (≥ 5) + `pytest-randomly` (≥ 3.15) + `dirty-equals` (≥ 0.8) +
  `pytest-timeout` (≥ 2.3), `ruff` (≥ 0.6), `pyright --strict` (≥ 1.1).
- Build/package: `uv` + `hatchling`, PEP 621 only.
- Removed: `jsonschema` (pydantic covers schema needs).
- Minimum Python: **3.11** (down from current `>=3.13`) — gives
  `asyncio.TaskGroup`, `asyncio.timeout`, `ExceptionGroup`, `Self`.

**Package layout** (from [`04-architecture.md`](04-architecture.md) §1):
single importable `arcp` package, not four sub-packages mirroring TS's
`@arcp/{core,client,runtime,sdk}`. Private modules use a leading
underscore (`arcp/_envelope.py`, `arcp/_runtime/*`, `arcp/_messages/*`).
The four public façades — `arcp`, `arcp.client`, `arcp.runtime`,
`arcp.middleware` — are the only re-export surfaces. Three middleware
adapters ship: `arcp.middleware.asgi`, `arcp.middleware.aiohttp`,
`arcp.middleware.otel` (from [`05-middleware.md`](05-middleware.md) §1).

**Concurrency.** `asyncio.TaskGroup` per session lifetime with four
explicit children (read pump, write pump, heartbeat ticker, lease
watchdog). Cancellation propagates via `CancelledError`; an
`asyncio.Event` (`ctx.signal`) is also exposed for poll-style agents
but is always set **before** `CancelledError` is raised. The heartbeat
ticker is the one task that **must not** be a child of the session
`TaskGroup`: see [`04-architecture.md`](04-architecture.md) §2 for the
load-bearing reason (a `HeartbeatLostError` propagating into the group
would cancel running jobs, violating spec §6.4).

**Test floor.** 90 % lines and branches (kept stricter than the
bootstrap's 87 % minimum because the current pyproject already enforces
90 %; the rewrite preserves that bar — [`07-tests.md`](07-tests.md)
§"Stack pick + dependencies" justifies). Five test layers under `tests/`:
`unit/envelope/`, `unit/messages/`, `state/`, `e2e/`, `conformance/`.
CI matrix: Python 3.11, 3.12, 3.13 on Linux + macOS.

**Doc target.** Plain Markdown under `docs/` (no Sphinx, no mkdocs).
Identical-across-SDKs frontmatter schema (`title`, `sdk`, `spec_sections`,
`order`, `kind`). Page counts: 9 v1.1 feature pages, **21** example
pages, 8 reference pages, 1 conformance page, plus overview / quickstart
/ concepts. Six Graphviz diagrams under `docs/diagrams/` rendered via
`make diagrams` + a pre-commit hook.

**Example count.** **21**, not 18 (the latter was the
[`02-current-audit.md`](02-current-audit.md) §5 stub-figure; superseded by
[`06-examples.md`](06-examples.md) §1, §6). Breakdown: 9 v1.0 core + 9
v1.1 feature + 3 host integrations (`host_asgi/`, `host_aiohttp/`,
`host_tracing/`).

## 2. Cross-phase contradictions & resolutions

Six seams surfaced during the parallel-phase write. All six are
resolved **in the source documents** — this section is the audit
trail. A reader who only opens `01`–`09` after the reconciliation pass
will see the resolved state directly; this section explains why each
file says what it says.

### 2.1 Example count drift: 14 → 18 → 21 — **resolved**

- **02-current-audit.md §5** projected "14 old → 18 new".
- **06-examples.md §1** counted the TS tree directly (22 dirs, not 23
  as TS's prose says) and produced **21** Python deliverables.

**21 is canonical.** Derivation: `bun/` is N/A in Python (−1);
`express/` + `fastify/` collapse to one `host_asgi/` (−1); a Python-
native `host_aiohttp/` is added because `aiohttp` is not ASGI (+1).
22 − 1 − 1 + 1 = 21. **Fixed:** `02-current-audit.md` §5 now reads
"14 old → 21 new" with the derivation inline; `08-docs-readme.md` §1
already aligned to 21 in its original draft.

### 2.2 Public API name placeholders in Phases 6 & 7 — **resolved**

`06-examples.md` and `07-tests.md` ran before `04-architecture.md`
appeared (the parallel dispatch raced). Each carried `TODO: align with
04-architecture.md §5` markers. The reconciliation pass replaced every
placeholder with the canonical name from
[`04-architecture.md` §5](04-architecture.md):

| Placeholder (old)                          | Canonical (now in 06 & 07)                                                       |
| ------------------------------------------ | -------------------------------------------------------------------------------- |
| `ARCPClient.connect(url, token=…)`         | `ARCPClient(...)` constructor + `await client.connect(transport)` explicit pair  |
| `handle.result`                            | `await handle.done` (awaitable property on `JobHandle`)                          |
| `ctx.cancelled` (event)                    | `ctx.signal: asyncio.Event` (set before `CancelledError`)                        |
| `client.list_jobs(filter=…)` async iter    | `await client.list_jobs(*, filter=..., limit=..., cursor=…) -> SessionJobsPayload` — single response, manual cursor follow-up |
| `client.subscribe(job_id, history=True)`   | `client.subscribe(job_id, *, history=False, from_event_seq=None) -> JobSubscription` |
| `ctx.stream_result()` as bare async CM     | `ResultStream` is now declared as an async CM in `04-architecture.md` §5.4 (`__aenter__`/`__aexit__` added; exit-path `close(more=False)` guaranteed) |
| `BearerVerifier.verify` placeholder        | Returns `Identity` model (Phase 4 §5 mirror of TS)                               |
| `validate_lease_op(now=…)` placeholder     | Now-injection seam on `_runtime/lease.py:validate_lease_op` (Phase 4 §1)         |

The reconciliation also pruned the closing "TODO: align with
04-architecture.md" section out of `06-examples.md` and replaced
`07-tests.md`'s preamble note about the missing 04/06 files. No
placeholder markers remain in `planning/v1.1/`.

### 2.3 Middleware API naming mismatch (04 ↔ 05 ↔ 08) — **resolved**

Three documents named the public middleware surface three different
ways. **Phase 5 wins** — it argued each name against a TS counterpart
in `typescript-sdk/packages/middleware/`. The canonical names are now
identical across all three docs:

| Module                         | Public symbol(s)                                                                                     |
| ------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `arcp.middleware.asgi`         | `arcp_asgi_app(runtime, *, allowed_hosts=None) -> ASGIApp`                                           |
| `arcp.middleware.aiohttp`      | `arcp_aiohttp_handler(runtime, *, allowed_hosts=None)`, `serve_arcp_aiohttp(runtime, *, host, port, path, allowed_hosts=None)` |
| `arcp.middleware.otel`         | `with_tracing(inner: Transport, *, tracer, send_span_name=None, recv_span_name=None) -> Transport`   |

**Fixed:** `04-architecture.md` §1's middleware tree and §6 public
re-export table now match these names; `08-docs-readme.md` §1's
`05-reference/` middleware pages now match these names. The earlier
generics (`serve`, `attach`, `route`, `install`) are gone.

### 2.4 Diagram location: `docs/assets/` vs `docs/diagrams/` — **resolved**

**Resolved to `docs/diagrams/`** for everything diagram-related (both
`.dot` source and paired `-light.svg` / `-dark.svg` outputs).
`docs/assets/` is reserved for non-diagram static media (favicons,
logos), per `09-diagrams.md` §"Anchors" and the new template-system
note in `09-diagrams.md` §1. **Fixed:** `08-docs-readme.md`'s
cross-reference to Phase 9 now points at `docs/diagrams/`.

### 2.5 Coverage floor: 87 % bootstrap minimum vs 90 % current — **resolved**

[`pyproject.toml:114`](../../pyproject.toml#L114) enforces
`--cov-fail-under=90`. [`07-tests.md`](07-tests.md) §"Stack pick" keeps
the 90 % floor; the bootstrap's 87 % is the **minimum acceptable**, not
the target. **Keep 90 %**; the carve-outs (`cli.py`, `__main__`, host
adapters with separate test surfaces) are documented in Phase 7. No
source-document edit was needed.

### 2.6 `arcp/examples` as a package vs separate `examples/` tree — **resolved**

`04-architecture.md` §1 originally included `arcp/examples/` as a
public namespace; `06-examples.md` §2 rule 1 ruled it out. **Phase 6
wins.** Examples live at the repo root in `examples/`, not under
`src/arcp/`. **Fixed:** `04-architecture.md` §1's tree now reads "(Examples
live at the repo root in `examples/`, NOT as a subpackage of `arcp`)";
the public re-export list in §6 no longer carries an `arcp.examples`
row.

### 2.7 Diagram styling: 3-color flat palette vs slate light/dark templates — **resolved**

The original `09-diagrams.md` committed to a flat 3-color palette
(`#dcfce7` / `#dbeafe` / `#fee2e2`) with `rankdir` per kind and one SVG
per diagram. The workspace standard at
[`docs/diagrams/README.md`](../../docs/diagrams/README.md) (copied from
the workspace template) defines a richer system: two-anchor (ENTRY
blue + HUB amber) with everything else neutral, slate palette in
paired light/dark `.dot` variants, cluster-fill-by-nesting, two-tier
edges, dashed-pink off-spine feedback paths, and a GitHub `<picture>`
embed that auto-switches by `prefers-color-scheme`. **Fixed:**
`09-diagrams.md` is rewritten end-to-end to the new system; the six
diagrams keep their semantic content but now ship as six
`<name>-{light,dark}.{dot,svg}` quartets. The template files are
staged under `docs/diagrams/diagram-template-{light,dark}.dot` for new
contributors to copy.

## 3. Ordered milestones

Each milestone is scoped to ship as one PR. The "files added/modified"
column names the load-bearing changes; ancillary edits (renaming
docstrings, updating `__all__`) are not enumerated. The "spec §"
column is the section the work lands.

| #   | Title                                          | Scope                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Spec §                                                                | Risk |
| --- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ---- |
| M1  | Project bootstrap                              | Edit `pyproject.toml` (deps from §1 above; `requires-python = ">=3.11"`; `[project.optional-dependencies] jwks`; drop `jsonschema`; add dev tools from §1). **No production code touched.** Run `uv lock` to regenerate `uv.lock`. (Cross-phase naming reconciliations from §2 are already done in the planning tree — see §2.2 / §2.3 / §2.6 / §2.7 — so M1 carries no doc edits.) | —                                                                     | L    |
| M2  | Envelope + wire constants realign              | Add `src/arcp/_envelope.py` (8-field §5.1 envelope, `arcp: "1"` constant, pydantic v2 frozen model with `from_wire`/`to_wire`, `extra="allow"` for §5.1 unknown-field rule). Add `src/arcp/_version.py` (`PROTOCOL_VERSION = "1"`, `V1_1_FEATURES`, `intersect_features`). Add `src/arcp/_errors.py` (15-class hierarchy from `04` §4). Add `src/arcp/_ulid.py`. **Delete** old `src/arcp/envelope.py`, `src/arcp/errors.py`, `src/arcp/version.py`. Tests under `tests/unit/envelope/` (`07` §2.1). | §5.1, §12                                                             | L    |
| M3  | Message types                                  | Add `src/arcp/_messages/session.py` (hello/welcome/error/bye/ping/pong/ack/list_jobs/jobs) and `src/arcp/_messages/execution.py` (job.submit/accepted/cancel/event/result/error/subscribe/subscribed/unsubscribe + 10 event-kind bodies). Add `src/arcp/_messages/__init__.py` registry. **Delete** `src/arcp/messages/{streaming,subscriptions,human,permissions,artifacts,telemetry}.py` and rewrite `session.py`/`execution.py`/`control.py`. Tests under `tests/unit/messages/` (`07` §2.2). | §6, §7, §8.2, §9.2                                                    | L    |
| M4  | Transport + store realign                      | Salvage `_transport/` verbatim (move from `transport/` to `_transport/`; add public re-export from `arcp/__init__.py`). Rewrite `src/arcp/_store/eventlog.py` schema to add session-scoped `event_seq` column + `read_since_seq` + ack-aware GC. Split idempotency into `src/arcp/_store/idempotency.py`. Update `src/arcp/_store/schema.sql`. Tests for transport round-trip and event-log replay.                                                                                              | §4, §6.3, §6.5, §8.3                                                  | M (event_seq atomicity invariant — see Risk R3) |
| M5  | Runtime v1.0 core                              | Add `src/arcp/_runtime/session.py` (SessionContext, `_stamp_and_emit` primitive from `04` §2, `next_event_seq`, resume), `_runtime/job.py` (Job state machine; emit_accepted / emit_event_kind / emit_result / emit_error; JobContext bar v1.1 surfaces), `_runtime/lease.py` (validate_lease_shape, validate_lease_op w/o constraints, is_lease_subset, canonicalize_target, compile_glob), `_runtime/pending.py` (salvage, rekey to envelope `id`). v1.0 state-machine tests (`07` §2.3).      | §6.1–§6.3, §6.7, §7.1–§7.4, §8.1–§8.3, §9.1–§9.4, §10                 | M (cancellation channel — Risk R1)              |
| M6  | Client v1.0 core                               | Add `src/arcp/_client/client.py` (handshake driver via `ARCPClient(...).connect(transport)`, request-id correlation, event tail), `_client/handles.py` (`JobHandle.done` awaitable property, `JobHandle.events()` iterator). v1.0 end-to-end happy path on `MemoryTransport` and `WebSocketTransport` (`tests/e2e/`).                                                                                                                                                                            | §6.1–§6.3, §6.7, §7.1–§7.4                                            | L    |
| M7  | v1.0 conformance: CLI, ASGI adapter, examples 1–9 | Rewrite `src/arcp/cli.py` (Click verbs: `serve`, `submit`, `tail`, `replay`). Add `src/arcp/middleware/asgi.py` (`arcp_asgi_app`). Add 9 v1.0 examples under `examples/{submit_and_stream,delegate,resume,idempotent_retry,lease_violation,cancel,stdio,vendor_extensions,custom_auth}/`. Add `tests/conformance/` rows for every v1.0 section.                                                                                                                                                  | §4, §6, §7, §8, §9, §10, §11, §15                                     | L    |
| M8a | v1.1: heartbeat + ack                          | Add `session.ping`/`session.pong`/`session.ack` payloads (`_messages/session.py` extends). Add `feature` flag `heartbeat` and `ack` to `V1_1_FEATURES`; wire intersection helper into `_runtime/session.py` + `_client/client.py`. Add heartbeat ticker (out-of-`TaskGroup` per `04` §2). Add `back_pressure` status emission. Examples: `heartbeat/`, `ack_backpressure/`.                                                                                                                       | §6.2, §6.4, §6.5                                                      | M (Risk R2 heartbeat coupling) |
| M8b | v1.1: list_jobs + subscribe                    | Add `session.list_jobs`/`session.jobs` payloads and runtime handler with `default_job_authorization_policy`. Add `job.subscribe`/`job.subscribed`/`job.unsubscribe`; subscriber fan-out in `SessionContext.send` using subscriber-scoped `event_seq` per `04` §2. Examples: `list_jobs/`, `subscribe/`. **Property test for subscriber seq invariant** (Risk R4).                                                                                                                                 | §6.2, §6.6, §7.6                                                      | **H (Risk R4 subscriber seq fan-out)** |
| M8c | v1.1: agent_versions                           | Add `parse_agent_ref` / `format_agent_ref` to `_messages/execution.py`. Add `register_agent_version` / `set_default_agent_version` to `ARCPRuntime`. Add rich `capabilities.agents: list[{name, versions, default?}]` shape to welcome. Raise `AgentVersionNotAvailableError` via `session.error` per §13.7. Example: `agent_versions/`.                                                                                                                                                          | §6.2, §7.5, §12                                                       | L    |
| M8d | v1.1: lease_expires_at                         | Add `lease_constraints.expires_at` to `JobSubmitPayload`/`JobAcceptedPayload`. Add `validate_lease_constraints` to `_runtime/lease.py`. Add `now=` clock injection to `validate_lease_op`. Add lease-expiry watchdog as a `_runtime/server.py` task per `04` §2 (one task per job). Add §9.4 subset rules. Example: `lease_expires_at/`.                                                                                                                                                          | §6.2, §9.4, §9.5, §12                                                 | M    |
| M8e | v1.1: cost.budget                              | Add `cost.budget` capability + `parse_budget_amount` (`currency:decimal` grammar). Add per-currency counter init at `job.accepted.payload.budget`. Add `Job.apply_cost_metric` decrement on `metric` events with `name` starting `cost.` and matching `unit`. Add `BUDGET_EXHAUSTED` surface (preferred: `tool_result.body.error`; fallback: `job.error`). Add debounced `cost.budget.remaining` emission. Add §9.4 child-budget subset rule. Example: `cost_budget/`.                            | §6.2, §9.4, §9.6, §12                                                 | M    |
| M8f | v1.1: progress + result_chunk                  | Add `progress` body schema (§8.2.1) and `JobContext.progress`. Add `result_chunk` body schema (§8.4); `JobContext.stream_result` async-context-manager writer; `JobHandle.chunks()` async iterator + `JobHandle.collect_chunks()`. Enforce "no mix inline+chunked" in `Job.emit_result`. Add §14 chunk-size cap with `INTERNAL_ERROR`. Examples: `progress/`, `result_chunk/`.                                                                                                                    | §8.2.1, §8.4, §14                                                     | M (Risk R5 result_chunk size cap) |
| M9  | Middleware (aiohttp + OTel) + host examples    | Add `src/arcp/middleware/aiohttp.py` (`arcp_aiohttp_handler` + `serve_arcp_aiohttp`). Add `src/arcp/middleware/otel.py` (`with_tracing(inner, *, tracer)` per Phase 5 §1.3, with v1.1 span attrs `arcp.lease.expires_at` / `arcp.budget.remaining`). Examples: `host_asgi/`, `host_aiohttp/`, `host_tracing/`.                                                                                                                                                                                    | §4.1, §11                                                             | L    |
| M10 | Docs + diagrams + README                       | Add `docs/` tree per Phase 8. Add six diagram pairs under `docs/diagrams/<name>-{light,dark}.{dot,svg}` per Phase 9, using the templates already staged at `docs/diagrams/diagram-template-{light,dark}.dot`. Add `make diagrams` target + `pre-commit` hook. Rewrite `README.md` per Phase 8 §3. Replace `CONFORMANCE.md` stub with the row-by-row matrix mirroring TS, citing `arcp/<path>.py:Lline`. Tag this commit `v1.1.0`-ready (release tagging is out of scope here).                    | §1–§16 (cited per page)                                               | L    |

**Total: 14 milestones.** M8a–M8f are deliberately split to keep PRs
reviewable; M8b carries the only H-risk in the plan and is the milestone
that pays for the property-test investment in M2/M3/M4.

## 4. Risks

Five named risks. Each names a concrete code path, the failure mode if
unaddressed, and the milestone that owns the mitigation.

- **R1 — Cancellation channel divergence.** `asyncio.CancelledError`
  semantics differ from TS `AbortSignal`; getting the cancel path wrong
  is silent (job tasks linger after the agent thinks it's done).
  Mitigation: Phase 4 §2 commits to `CancelledError` as the primary
  channel with `ctx.signal: asyncio.Event` as the cooperative alternate;
  the `cancel/` example demonstrates the required idiom; `tests/state/`
  asserts a `with pytest.raises(asyncio.CancelledError):` shape on the
  cancel path. Owned by **M5** (runtime core) and tested in **M7**
  (`cancel/` example + conformance row).

- **R2 — Heartbeat tied into session `TaskGroup`.** If the heartbeat
  loop is a child of the session `TaskGroup` and raises
  `HeartbeatLostError`, the group cancels every sibling, terminating
  running jobs — violating spec §6.4 ("runtime MUST NOT terminate jobs
  on heartbeat loss"). Mitigation: Phase 4 §2 spawns the heartbeat
  ticker via `asyncio.create_task()` **outside** the session
  `TaskGroup` and signals outcome through
  `SessionContext.heartbeat_outcome: asyncio.Future[None]`. Owned by
  **M8a** with a regression test under `tests/state/`.

- **R3 — `event_seq` atomicity.** §8.3 requires session-scoped,
  monotonic, gap-free seqs. Any `await` between observing the counter
  and pushing the envelope onto the send queue gives asyncio a context
  switch and a chance to interleave. Mitigation: Phase 4 §2's
  `_stamp_and_emit` invariant — no `await` between `_next_event_seq()`
  and `_send_queue.put_nowait(env)`; the runtime grep for direct
  `transport.send(...)` of seq-bearing envelopes is part of the M2
  conformance gate. Tested by a Hypothesis property in **M2**
  (`tests/unit/envelope/test_envelope_roundtrip.py` and `tests/state/`).

- **R4 — Subscriber seq fan-out (H-risk).** §7.6 history replay must use
  the **subscriber's** event-seq counter, not the submitter's. Wiring
  it wrong is invisible until a subscriber resumes and observes seq
  collisions with live events. Mitigation: Phase 4 §1 puts subscriber
  fan-out in `SessionContext.send` (each subscriber holds its own
  counter); `tests/state/` carries a parametrized test that drives N
  subscribers and asserts each subscriber's seq stream is independent
  and gap-free. Owned by **M8b** (also the milestone gated on this
  test passing).

- **R5 — Unbounded `result_chunk` memory.** §14 RECOMMENDS chunk-size
  and total-streamed caps; an absence is a memory-exhaustion vector on
  both ends. Mitigation: enforce a per-chunk cap (default 1 MB,
  configurable on `ARCPRuntime`) in `Job.emit_event_kind` for the
  `result_chunk` kind; reject overruns with `INTERNAL_ERROR` per §14.
  Owned by **M8f**.

Additional process note: the parallel-dispatch race in this planning
round originally produced two documents (Phase 6, Phase 7) with
`TODO: align with 04-architecture.md` markers (§2.2 above). Those
reconciliations are already applied in the planning tree — every
TODO marker is gone, and `06-examples.md` §7 lists the anchored names
explicitly. M1 carries no doc edits as a result.

## 5. Explicit non-goals

The migration **does not** ship any of the following. Each is listed so
a reviewer asking "did you forget X?" can grep "non-goal" and confirm
"no, deliberately deferred":

- **Job pause / unpause.** Spec §"Not in v1.1 (deferred)".
- **Job priority / scheduling hints.** Same.
- **Federation across runtimes.** Same.
- **Streaming-token surface for LLM outputs.** Same — out of ARCP's
  scope; agents call MCP/LLM SDKs and emit `result_chunk` events for
  large final results, not per-token deltas.
- **Persistent idempotency store.** Phase 4 §1 ships an in-memory
  `_store/idempotency.py` (TTL sweep). Production deployments inject a
  persistent map; mirrors TS reference's "Intentional deferral".
- **`anyio` / `trio` interop.** Phase 3 §4 rejects it for cancellation-
  semantics reasons. Single async runtime — stdlib `asyncio`.
- **Per-framework ASGI middleware** (separate Starlette / FastAPI /
  Litestar / Quart adapters). Phase 5 §2 rejects — ASGI 3's `websocket`
  scope is the abstraction; one adapter covers all four frameworks.
- **Flask / Tornado / Django Channels adapters.** Phase 5 §2 rejects.
- **Bun runtime adapter.** N/A in Python (Bun is a JS runtime).
- **Mutation testing.** Phase 3 §11 declines `mutmut`/`cosmic-ray` as
  pre-stability tooling; reconsider only after coverage > 95 %.
- **Auto-generated API reference (Sphinx/mkdocs).** Phase 8 §"Hard
  rules" rejects — Markdown is hand-written from Phase 4's signatures.
- **JSON Schema documents for the wire** (as a shipped artifact). Phase
  3 §1 notes pydantic's `TypeAdapter(...).json_schema()` produces them
  on demand; no published-schema artifact in v1.1.
- **Published-package version bump beyond v1.1.0.** Release tagging
  is operational, out of this plan's scope.

## 6. Open questions for the human reviewer

These are the calls the plan cannot make alone. Each is concrete; each
blocks a specific milestone.

1. **`stream_result` as async CM vs explicit `await stream.close()`?**
   Resolved in the reconciliation pass — `ResultStream` in
   `04-architecture.md` §5.4 now declares `__aenter__`/`__aexit__`;
   `06-examples.md` §4 anchors the demonstrated idiom; `07-tests.md`
   carries the exception-path regression test. Confirm the rationale
   ("must finalize on exception") is the right tradeoff over the
   simpler explicit-close form. **No longer blocks M8f.**

2. **`list_jobs` pagination surface: single response or async iterator
   of pages?** Resolved — single `SessionJobsPayload` response (matches
   TS, mirrors `04-architecture.md` §5.1). `06-examples.md` §1b's
   `list_jobs/` row now demonstrates manual `cursor=` follow-up.
   Confirm. **No longer blocks M8b.**

3. **`host_aiohttp/` example: ship or fold?** Phase 6 §1c adds it; Phase
   5 §1.2 commits to the adapter. The combined cost is one example
   directory + one middleware module. The audience is non-trivial
   (PyPI download metrics put `aiohttp` among the top async-web servers
   in 2026), so the recommendation is **ship**. Confirm. **Blocks M9.**

4. **TS reference example count drift: 23 (prose) vs 22 (tree).** TS's
   own `examples/README.md` says "Twenty-three" but the tree has 22.
   Phase 6 §1 surfaced this. Either a TS-side fix (rename the prose) or
   confirmation that 22 is the canonical count — the Python plan
   commits to 21 and is unblocked, but downstream cross-SDK
   conformance docs should agree on a single number. **Does not block
   any milestone; resolve before docs publication (M10).**

5. **Wire-level `traceparent` extension key string.** Phase 5 §5 says
   the key is `"x-vendor.opentelemetry.tracecontext"` (from TS).
   Confirm this is the canonical string across SDKs — if any other SDK
   ships a different key (e.g. `"x-vendor.otel.tracecontext"`),
   distributed tracing breaks across language boundaries. **Blocks
   M9** (otel middleware ships with this string literal).

6. **Heartbeat default interval.** Phase 4 §5 defaults
   `heartbeat_interval_sec=30`, mirroring spec §6.4's example. The
   `heartbeat/` example uses 5 s for fast feedback (Phase 6 §1b). Both
   are fine; the question is whether the default ships as 30 (matches
   TS) or as a smaller number for better default detection.
   **Recommendation: 30** (matches TS, matches the spec example).
   Confirm. **Blocks M8a.**

7. **Coverage carve-out for the OTel middleware.** Phase 7 §6 carves
   out `cli.py` and `__main__`; `middleware/otel/__init__.py` is
   borderline. The adapter is the only module that requires
   `opentelemetry-sdk` to test end-to-end. Either an in-memory exporter
   covers it (recommended) or it gets a documented carve-out.
   **Recommendation: in-memory exporter; no carve-out.** Confirm.
   **Blocks M9.**

8. **Release tagging strategy.** Out of plan scope, but the milestones
   above ship in 14 PRs; whether they batch into one `v1.1.0` tag at
   M10 or ship incremental `v1.1.0-alpha.N` tags is an operational
   call. **Recommendation: alpha tags from M5 onward** (one
   conformance-test-runnable artifact per milestone); final v1.1.0 at
   M10. **Operational; does not block milestone code merges.**

---

This synthesis is the document any future contributor opens first.
Phases 01–09 stand as the load-bearing references; this file is the
map.
