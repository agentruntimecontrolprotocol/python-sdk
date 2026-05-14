# 09 — Diagrams

Diagrams ship under [`docs/diagrams/`](../../docs/diagrams/) as
Graphviz `.dot` source paired with rendered **light + dark SVGs**.
GitHub serves the matching SVG via a `<picture>` element with
`prefers-color-scheme`. The system, palette, and `.dot` templates are
the workspace standard documented in
[`docs/diagrams/README.md`](../../docs/diagrams/README.md) (copied from
the workspace template at first commit of this plan).

Anchors:

- Wire surface: [`spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md).
- v1.1 delta and feature flags: [`01-spec-delta.md`](./01-spec-delta.md).
- Post-realign module tree: [`04-architecture.md` §1](./04-architecture.md).
  The diagrams cite that tree's underscore-prefixed `_messages` /
  `_runtime` / `_client` / `_envelope` / `_errors` / `_version` /
  `_store` / `_transport` / `_auth` / `_extensions` / `_logger` /
  `_ulid` modules and the public façades `arcp/{client,runtime,middleware}/`.
- Docs page anchors: page paths come from
  [`08-docs-readme.md` §1](./08-docs-readme.md) — `docs/02-concepts.md`,
  `docs/03-features/<flag>.md` (one file per feature flag).
- Diagram template howto: [`docs/diagrams/README.md`](../../docs/diagrams/README.md)
  is authoritative for palette, design rules, and embed snippets;
  this file commits to the diagrams the SDK ships and what each one
  contains.

## 1. The template system in one paragraph

Each diagram is two `.dot` files (one `-light.dot`, one `-dark.dot`)
with identical structure — same nodes, edges, cluster boundaries —
differing only in fill / border / text colors from the slate palette.
Both render to SVG with `bgcolor="transparent"`. The light/dark pair is
embedded in Markdown via `<picture><source media="(prefers-color-scheme:
dark)" srcset="<name>-dark.svg"><img src="<name>-light.svg"></picture>`.
The five **design rules** (from [`docs/diagrams/README.md`](../../docs/diagrams/README.md)
§"Design rules") apply to every diagram below without exception:

- **Two anchors max.** One ENTRY (blue `#3B82F6`) and one HUB (amber
  `#F59E0B`) per diagram. Everything else uses defaults.
- **Two-tier edges.** Primary spine at `penwidth=1.2` with ink-500 /
  slate-400; secondary wiring recedes at `penwidth=1.0` with ink-300 /
  slate-600.
- **Cluster fills signal nesting.** Outer/primary uses ink-100 /
  slate-900; inner/secondary uses ink-50 / slate-800.
- **Data stores use `shape=cylinder`.** Everything else is a rounded
  box.
- **Feedback / async / return paths** use dashed pink edges with a
  label and `constraint=false`.

The diagrams below name the ENTRY and HUB explicitly, list the
clusters, and note any cylinder data stores. **Do not** override the
template's node/edge defaults; if a diagram needs styling not described
in the template, the diagram is too complex for the docs site.

## 2. The six diagrams

Each entry below names: filenames (light + dark), embed page,
**ENTRY** anchor, **HUB** anchor, clusters, the content the reader
learns in 10 seconds, and the spec § the diagram references.

### 2.1 `arch-overview-{light,dark}.dot` — module dependency graph

- **Filenames**: `docs/diagrams/arch-overview-light.dot` /
  `arch-overview-dark.dot`.
- **Render**: `dot -Tsvg docs/diagrams/arch-overview-light.dot -o
  docs/diagrams/arch-overview-light.svg` (and the `-dark` pair).
- **Embedded in**: [`docs/00-overview.md`](../../docs/00-overview.md)
  hero image; also [`docs/02-concepts.md`](../../docs/02-concepts.md)
  section "How the SDK is organised".
- **Layout**: `rankdir=TB`. `splines=spline`. `compound=true`.
- **ENTRY** (blue): `ARCPClient` — external code's entry to the SDK.
- **HUB** (amber): `Dispatcher` (inside `cluster_runtime`) — the
  central handler everything routes through (mirrors the worked
  example in [`docs/diagrams/README.md`](../../docs/diagrams/README.md)).
- **Clusters**:
  - `cluster_transport` (outer, ink-100 / slate-900): three side-by-
    side boxes via the same-rank trick — `WebSocket`, `stdio`,
    `in-memory`. Maps to `arcp/_transport/{websocket,stdio,in_memory}.py`.
  - `cluster_runtime` (inner, ink-50 / slate-800): `HandshakeDriver`,
    `Dispatcher` (HUB), `JobManager`, `SubscriptionFanout`,
    `LeaseManager`, `PendingRegistry`, `EventLog` (cylinder, SQLite
    subtitle). Maps to `arcp/_runtime/*` plus `arcp/_store/eventlog.py`.
- **Spine edges** (primary, ink-500): `ARCPClient → WebSocket`
  (`lhead=cluster_transport`, `dir=both`, label `envelopes`);
  `WebSocket → HandshakeDriver` (`ltail=cluster_transport`,
  `dir=both`, label `envelopes`); `HandshakeDriver → Dispatcher`;
  `Dispatcher → JobManager`; `Dispatcher → SubscriptionFanout`;
  `Dispatcher → LeaseManager`; `Dispatcher → PendingRegistry`.
- **Secondary edges** (ink-300): `JobManager → EventLog`;
  `SubscriptionFanout → EventLog`; `JobManager → PendingRegistry`.
- **Feedback edge** (dashed pink, `constraint=false`):
  `PendingRegistry → Dispatcher` labelled `resolve` — the
  request_id correlation seam from
  [`04-architecture.md` §1](./04-architecture.md) `_runtime/pending.py`.
- **What the reader learns in 10 seconds**: the SDK is organised
  around one HUB (Dispatcher) fed by one ENTRY (ARCPClient through
  three transports); persistent state lives in one cylinder
  (EventLog); pending requests round-trip through the dashed-pink
  return path. The two clusters make the boundary between transport
  and runtime visible at a glance.
- **Spec §**: §4 (Transport), §5 (Wire Format), §7 (Jobs), §8 (Events).

### 2.2 `session-lifecycle-{light,dark}.dot` — session state machine

- **Filenames**: `docs/diagrams/session-lifecycle-{light,dark}.dot`.
- **Embedded in**: [`docs/02-concepts.md`](../../docs/02-concepts.md)
  section "Session lifecycle".
- **Layout**: `rankdir=TB`. `splines=spline`. No `compound`.
- **ENTRY** (blue): `OPENING` — the state right after the transport
  is accepted, before any envelope flows.
- **HUB** (amber): `WELCOMED` — the steady-state where job traffic
  happens; everything else is a transitional state around it.
- **Clusters**: none. State machines read more cleanly without
  cluster boundaries — the rounded boxes are the states themselves.
- **Other nodes**: `HELLO_SENT`, `RESUMING`, `CLOSING`, `CLOSED`.
- **Spine edges** (primary, ink-500, labelled with the wire verb):
  `OPENING → HELLO_SENT` (`session.hello`);
  `HELLO_SENT → WELCOMED` (`session.welcome`);
  `WELCOMED → CLOSING` (`session.bye`);
  `CLOSING → CLOSED` (transport close).
- **Secondary edges** (ink-300): `WELCOMED → RESUMING` (label
  `transport drop`); `RESUMING → WELCOMED` (label
  `session.hello{resume}` per §6.3).
- **Feedback edge** (dashed pink, `constraint=false`):
  `WELCOMED → CLOSING` labelled `HEARTBEAT_LOST` — the §6.4 auto-
  close path on two missed intervals; the dashed pink signals it
  is the abnormal-termination path, distinct from `session.bye`.
- **What the reader learns in 10 seconds**: there is one
  load-bearing state (WELCOMED, the HUB); resume returns to it,
  bye / heartbeat-loss leave it; the spec's distinction between
  graceful close and heartbeat-lost close is the dashed-pink edge.
- **Spec §**: §6.2 (hello/welcome), §6.3 (resume), §6.4 (heartbeats),
  §6.7 (bye).

### 2.3 `job-lifecycle-{light,dark}.dot` — job state machine with v1.1

- **Filenames**: `docs/diagrams/job-lifecycle-{light,dark}.dot`.
- **Embedded in**: [`docs/03-features/lease-expires-at.md`](../../docs/03-features/lease-expires-at.md)
  and [`docs/03-features/cost-budget.md`](../../docs/03-features/cost-budget.md)
  (the two v1.1 features that add new transitions to this machine).
- **Layout**: `rankdir=TB`. `splines=spline`. `compound=false`.
- **ENTRY** (blue): `Submit` — the client's `job.submit` call. Not a
  job state itself; it's the off-machine trigger that produces the
  first state.
- **HUB** (amber): `running` — the state every other transition
  passes through. Aligns with §7.3.
- **Other nodes** (rounded boxes, default fills): `pending`,
  `success`, `error`, `cancelled`, `timed_out`. The four terminal
  states are nodes; they have no outgoing edges.
- **Spine edges** (primary, ink-500): `Submit → pending`
  (`job.submit`); `pending → running` (`job.accepted`);
  `running → success` (`job.result{final_status:"success"}`);
  `running → cancelled` (`job.cancel` → `job.error{final_status:"cancelled"}`).
- **Secondary edges** (ink-300): `running → timed_out`
  (label `max_runtime_sec elapsed`); `running → error`
  (label `job.error{final_status:"error"}`); a separate
  `running → error` (label `BUDGET_EXHAUSTED §9.6`, v1.1-only); and
  `running → error` (label `LEASE_EXPIRED §9.5`, v1.1-only). The two
  v1.1-only labels make explicit which transitions are new in this
  spec revision.
- **Feedback edge** (dashed pink, `constraint=false`):
  `running → running` self-loop labelled `subscribe / progress / chunk`
  — the v1.1 channels (§7.6, §8.2.1, §8.4) that do **not** transition
  the state machine; they ride alongside it. The dashed pink emphasises
  they are streaming events, not lifecycle transitions.
- **What the reader learns in 10 seconds**: four terminals, one HUB
  (`running`), v1.1 adds two new reasons to reach the `error`
  terminal (budget, lease) and three new streaming kinds that do
  not change states. Clean separation of "lifecycle moves" vs
  "events on the wire".
- **Spec §**: §7.1, §7.3, §7.4, §9.5, §9.6, §7.6, §8.2.1, §8.4.

### 2.4 `capability-negotiation-{light,dark}.dot` — feature intersection

- **Filenames**: `docs/diagrams/capability-negotiation-{light,dark}.dot`.
- **Embedded in**: [`docs/03-features/capability-negotiation.md`](../../docs/03-features/capability-negotiation.md).
- **Layout**: `rankdir=LR` (sequence shape). `compound=true`.
- **ENTRY** (blue): `Client` (left lane, single node).
- **HUB** (amber): `Runtime` (right lane, single node).
- **Clusters**: none — this is a sequence-style diagram with two
  vertical lanes implemented as two top-level nodes plus rank
  control on the message nodes.
- **Message nodes** (rounded boxes, no cluster):
  - `hello_features` labelled `session.hello\\nfeatures = [heartbeat, ack, list_jobs, subscribe, ...]`
  - `welcome_features` labelled `session.welcome\\nfeatures = [heartbeat, ack, agent_versions]`
  - `intersection` labelled `negotiated = {heartbeat, ack}`
    (a default node, neither anchor, sitting below the two message
    nodes to read as the conclusion).
- **Spine edges** (primary, ink-500): `Client → hello_features`;
  `hello_features → Runtime`; `Runtime → welcome_features`;
  `welcome_features → Client`. Force order via
  `{ rank=same; hello_features; welcome_features; }` so the two
  messages sit on one row.
- **Secondary edges** (ink-300): `hello_features → intersection`;
  `welcome_features → intersection`.
- **Feedback edge** (dashed pink, `constraint=false`): an
  off-spine note from `intersection` back to `Client` labelled
  `client.has_feature("subscribe") → False` — the example
  consequence of intersection (subscribe was offered by client but
  not by runtime, so it is not in the negotiated set).
- **What the reader learns in 10 seconds**: two `features` lists go
  on the wire; the negotiated set is their intersection;
  `has_feature` (Phase 4 §5.1) reflects that intersection; either
  peer using a feature outside the intersection fails closed.
- **Spec §**: §6.2 (the entire compatibility hinge per
  [`01-spec-delta.md` §3](./01-spec-delta.md)).

### 2.5 `heartbeat-ack-{light,dark}.dot` — §6.4 + §6.5 flow

- **Filenames**: `docs/diagrams/heartbeat-ack-{light,dark}.dot`.
- **Embedded in**: [`docs/03-features/heartbeats.md`](../../docs/03-features/heartbeats.md)
  and [`docs/03-features/event-ack.md`](../../docs/03-features/event-ack.md).
- **Layout**: `rankdir=LR`. `compound=false`.
- **ENTRY** (blue): `Client` (left lane node).
- **HUB** (amber): `Runtime` (right lane node).
- **Message nodes** (rounded boxes, defaults):
  - `idle_30s` (label `30s idle`).
  - `ping` (label `session.ping\\n{nonce, sent_at}`).
  - `pong` (label `session.pong\\n{ping_nonce, received_at}`).
  - `ack` (label `session.ack\\n{last_processed_seq: 1827}`).
  - `lag_detected` (label `consumer lag > threshold`).
  - `back_pressure` (label `job.event{kind: status,\\nbody.phase: "back_pressure"}`).
- **Spine edges** (primary, ink-500): `Client → idle_30s →
  ping → Runtime`; `Runtime → pong → Client`. Force the two
  message rows with `{ rank=same; ping; pong; }`.
- **Secondary edges** (ink-300): `Client → ack → Runtime` (one
  rank below the heartbeat row); `Runtime → lag_detected →
  back_pressure → Client`.
- **Feedback edge** (dashed pink, `constraint=false`):
  `pong → Runtime` labelled `not in event_seq` — the load-bearing
  fact from §6.4 that pings/pongs do not consume sequence numbers.
  A second feedback edge from `ack → Runtime` labelled
  `not in event_seq` reinforces the same property for §6.5.
- **What the reader learns in 10 seconds**: ping/pong is the
  liveness check, runs both directions; ack is one-way client→
  runtime; back-pressure is runtime's reply when the consumer
  lags; none of these three consume `event_seq`.
- **Spec §**: §6.4, §6.5, §8.3 (event_seq invariant).

### 2.6 `result-chunk-progress-{light,dark}.dot` — §8.4 + §8.2.1 stream

- **Filenames**: `docs/diagrams/result-chunk-progress-{light,dark}.dot`.
- **Embedded in**: [`docs/03-features/result-chunk.md`](../../docs/03-features/result-chunk.md)
  and [`docs/03-features/progress.md`](../../docs/03-features/progress.md).
- **Layout**: `rankdir=LR`. `compound=false`.
- **ENTRY** (blue): `Agent` (leftmost lane node).
- **HUB** (amber): `Runtime` (middle lane node) — the
  load-bearing intermediary; everything routes through it.
- **Other lane node** (default, not an anchor): `Client` (rightmost).
- **Message nodes** (rounded boxes, defaults), three rows top to
  bottom:
  - Row 1: `tool_call_pair` (label `tool_call → tool_result\\nevent_seq N, N+1`).
  - Row 2: `progress_event` (label `progress\\n{current, total, units}\\nevent_seq N+2`).
  - Row 3: `chunk_0_29` (label `result_chunk × 30\\n{result_id, chunk_seq, data, more: true}`).
  - Row 4: `chunk_final` (label `result_chunk\\n{more: false}`).
  - Row 5: `job_result` (label `job.result\\n{final_status: success,\\nresult_id, result_size}`).
- **Spine edges** (primary, ink-500), top to bottom:
  `Agent → tool_call_pair → Runtime → Client`;
  `Agent → progress_event → Runtime → Client`;
  `Agent → chunk_0_29 → Runtime → Client`;
  `Agent → chunk_final → Runtime → Client`;
  `Agent → job_result → Runtime → Client`.
  Use `{ rank=same; tool_call_pair; progress_event; chunk_0_29;
  chunk_final; job_result; }` only loosely — the rank-same
  forces them onto the same column, the natural vertical order
  comes from declaration order with `nodesep` separating rows.
- **Secondary edges** (ink-300): none — every message in the
  sequence is part of the main spine.
- **Feedback edge** (dashed pink, `constraint=false`):
  `Client → Runtime` labelled `assemble bytes by result_id\\nuntil more=false`
  — the client's reassembly invariant from §8.4 ("the assembled
  result is the concatenation of the chunks' decoded `data` in
  `chunk_seq` order"). Placed off-spine so it does not distort
  the message column.
- **What the reader learns in 10 seconds**: chunks ride the same
  `job.event` envelope stream as progress and tool events; the
  terminal `job.result` references the streamed `result_id`; the
  client reassembles in `chunk_seq` order; inline `result` and
  `result_chunk` are mutually exclusive in one job.
- **Spec §**: §8.2.1, §8.4, §14 (chunk-size cap).

## 3. What does NOT get a diagram

Stated explicitly so the next contributor doesn't fill `docs/diagrams/`
with weak material:

- **Auth flow.** One verb (`session.hello.payload.auth.token`), one
  failure mode (`UNAUTHENTICATED` at handshake). Prose covers it.
- **Idempotency flow.** Single store lookup; one error code
  (`DUPLICATE_KEY`). The §7.2 spec text plus the example narrative is
  enough.
- **Delegation subset rule.** Algorithmic (set comparison + budget
  arithmetic + expiry inequality). A diagram would not encode the
  algorithm; the unit test plus §9.4 prose does.
- **Transport stack.** One box per transport is not a diagram; the
  table in `docs/02-concepts.md` carries the same information in
  less visual cost.
- **Pre-realign / draft-01 wire.** Not part of this SDK's published
  surface — see [`02-current-audit.md`](./02-current-audit.md). No
  diagram of historical state.

## 4. Render pipeline

- `.dot` source and `.svg` outputs are **both** committed under
  [`docs/diagrams/`](../../docs/diagrams/). The shared docs site
  serves the SVGs; the SVGs ship in the published-docs build.
- One `make diagrams` target at the repo root re-renders every pair
  (`*-light.dot → *-light.svg` and `*-dark.dot → *-dark.svg`). The
  target shells out to `dot -Tsvg` per file; no Python runner is
  needed.
- **`pre-commit`** runs `make diagrams` when any `docs/diagrams/*.dot`
  file is staged and re-stages the resulting `.svg`s. The hook fails
  the commit if `dot` is not installed (Graphviz is a developer
  prerequisite, noted in `README.md`'s "Development" section per
  [`08-docs-readme.md` §3](./08-docs-readme.md)). No CI step
  re-renders diagrams; the committed `.svg` is the source of truth
  for the docs build.
- The template at
  [`docs/diagrams/diagram-template-light.dot`](../../docs/diagrams/diagram-template-light.dot)
  and [`docs/diagrams/diagram-template-dark.dot`](../../docs/diagrams/diagram-template-dark.dot)
  is the starting point for any new diagram. New contributors copy
  the template pair, edit **only** the example section, and run
  `make diagrams`.

## 5. Cross-SDK alignment

This system (slate palette, two-anchor rule, light+dark `<picture>`
embed) is the workspace standard described in
[`docs/diagrams/README.md`](../../docs/diagrams/README.md). When the
TypeScript and other SDKs ship their own `09-diagrams.md`, they
adopt the same template tree; the diagrams above are the Python
SDK's specific instantiations, not a divergent style.
