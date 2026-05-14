# 01 — Spec Delta: v1.0 → v1.1

Source: [`../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md).
v1.1 is **additive** over v1.0 (`../spec/docs/draft-arcp-02.md`); the envelope
constant `arcp` remains `"1"`, no v1.0 verb is removed, no field is renamed.
Every new surface is gated by a feature flag in
`session.hello.payload.capabilities.features` ∩
`session.welcome.payload.capabilities.features`.

This document is **only** the v1.0 → v1.1 diff. The wholly separate problem
of realigning this SDK from its current draft-01 / `RFC-0001-v2` wire to
v1.0 lives in `02-current-audit.md`.

## 1. Addition table

Spec §, message/feature, MUST/SHOULD/MAY level, and impact on a v1.0
Python client or runtime that does **not** advertise the new feature. The
"impact" column says whether a v1.0 peer is forced to change. v1.1 is
designed so the answer is "no" for every row; this column is the
verification, not a hope.

| §       | Message / feature                                              | Level | Additive vs breaking for v1.0 peer |
| ------- | -------------------------------------------------------------- | ----- | ---------------------------------- |
| §6.2    | `capabilities.features: string[]` on hello & welcome           | MUST (when feature set is non-empty) | Additive — v1.0 omits, runtime sees `[]`, no v1.1 feature negotiated |
| §6.2    | Rich `capabilities.agents: Array<{name,versions,default?}>`    | MAY   | Additive — v1.0 §5.1 says unknown top-level fields MUST be ignored; v1.1 keeps the flat string[] shape as a valid fallback for v1.0 runtimes |
| §6.2    | `session.welcome.payload.heartbeat_interval_sec: int`          | SHOULD (when `heartbeat` negotiated) | Additive — v1.0 client ignores it |
| §6.4    | `session.ping { nonce, sent_at }` / `session.pong { ping_nonce, received_at }` | MUST respond to ping within interval (when `heartbeat` negotiated) | Additive — never sent if feature not negotiated; never counted in `event_seq` |
| §6.4    | `HEARTBEAT_LOST` close after 2 idle intervals                  | MAY   | Additive |
| §6.5    | `session.ack { last_processed_seq }`                           | MAY send; MUST NOT free unacked events under buffer limit (when `ack` negotiated) | Additive — purely advisory; resume still requires client-side `last_event_seq` |
| §6.5    | Back-pressure `status` event when consumer lags                | MAY   | Additive — uses existing `status` kind |
| §6.6    | `session.list_jobs { filter?, limit?, cursor? }`               | MAY send (when `list_jobs` negotiated) | Additive |
| §6.6    | `session.jobs { request_id, jobs[], next_cursor }`             | MUST respond when `list_jobs` negotiated | Additive |
| §7.1    | `job.submit.payload.lease_constraints.expires_at: ISO8601-UTC` | MAY   | Additive — absent ⇒ no expiration |
| §7.1    | `job.accepted.payload.lease_constraints` & `.budget`           | MUST echo when present in submit | Additive |
| §7.5    | `agent ::= name ("@" version)?` grammar                        | MUST parse if `agent_versions` negotiated | Additive — bare names continue to work |
| §7.5    | Default-version resolution from `welcome.capabilities.agents`  | SHOULD | Additive |
| §7.6    | `job.subscribe { job_id, from_event_seq?, history? }`          | MAY send (when `subscribe` negotiated) | Additive |
| §7.6    | `job.subscribed { current_status, agent, lease, parent_job_id, trace_id, subscribed_from, replayed }` | MUST respond | Additive |
| §7.6    | `job.unsubscribe { job_id }`                                   | MAY send | Additive |
| §7.6    | Subscribers MUST NOT have cancel authority                     | MUST  | Additive — tightens authorization for the new verb only |
| §8.2    | `progress` event kind                                          | Reserved name (when `progress` negotiated) | Additive — v1.0 §8.2 says unknown kinds may be ignored |
| §8.2.1  | `progress` body `{ current, total?, units?, message? }`        | MUST validate when negotiated | Additive |
| §8.4    | `result_chunk` event kind                                      | Reserved name (when `result_chunk` negotiated) | Additive |
| §8.4    | `result_chunk` body `{ result_id, chunk_seq, data, encoding ∈ {utf8,base64}, more }` | MUST when negotiated | Additive |
| §8.4    | `job.result.payload.result_id` / `result_size`                 | MUST when streamed | Additive — v1.0 inline `result` path unchanged |
| §8.4    | MUST NOT mix inline `result` and `result_chunk` in one job     | MUST  | Additive constraint on the new path |
| §9.4    | Child `cost.budget` ≤ parent remaining per currency            | MUST when delegating with budgets | Additive — only triggers if `cost.budget` is present |
| §9.4    | Child `lease_constraints.expires_at` ≤ parent's                | MUST when delegating with expiry | Additive |
| §9.4    | Implicit expiry inheritance when child omits constraints       | MUST  | Additive |
| §9.5    | `lease_constraints.expires_at` is ISO 8601 UTC, MUST be future | MUST when present | Past values rejected with `INVALID_REQUEST` |
| §9.5    | Operations at/after `expires_at` MUST fail `LEASE_EXPIRED`     | MUST when negotiated | New error code (additive — see §12) |
| §9.5    | Runtime MUST emit `job.error{LEASE_EXPIRED}` when lease elapses while running | MUST | Additive |
| §9.5    | Renewal NOT supported in v1.1                                  | MUST NOT  | Additive constraint |
| §9.6    | `cost.budget` capability — amounts `currency:decimal`          | MUST validate amount grammar when negotiated | Additive |
| §9.6    | Per-currency counters initialized at `job.accepted.payload.budget` | MUST when negotiated | Additive |
| §9.6    | Counters decrement on `metric` events with `name` starting `cost.` and matching `unit` | MUST when negotiated | Additive — v1.0 `metric` body shape unchanged |
| §9.6    | Negative metric values MUST NOT decrement                      | MUST  | Additive |
| §9.6    | Operations through the lease fail `BUDGET_EXHAUSTED` when any counter ≤ 0 | MUST when negotiated | New error code |
| §9.6    | Runtime MAY emit `cost.budget.remaining` metric                | MAY   | Additive |
| §11     | OTel span attrs `arcp.lease.expires_at`, `arcp.budget.remaining` | SHOULD when present | Additive |
| §12     | `AGENT_VERSION_NOT_AVAILABLE`                                  | MUST when version pinning fails | New error — non-retryable |
| §12     | `LEASE_EXPIRED`                                                | MUST   | New error — non-retryable |
| §12     | `BUDGET_EXHAUSTED`                                             | MUST   | New error — non-retryable |
| §14     | Subscribe-scope (same principal default; auditable broadening) | MUST   | Tightens deployment defaults for the new verb |
| §14     | Chunk-size cap (e.g. 1 MB) and total streamed-result cap       | SHOULD | Additive — exceedance ⇒ `INTERNAL_ERROR` |

Backward-compatibility verification (the rules that make every row above
"additive"):

- v1.0 §5.1 already requires implementations to **ignore unknown top-level
  envelope fields**; v1.1 explicitly extends this (§5 lead-in: a v1.0 client
  receiving a v1.1-only message type SHOULD ignore it). Quoted because it
  pins the wire's forward-compat contract:
  > a v1.0 client receiving a v1.1-only message type SHOULD ignore it
  > rather than treating the connection as broken.
- Effective feature set is the **intersection** of the two `features`
  arrays. Either peer MUST NOT use a feature outside that set
  (§6.2). This is the entire compatibility hinge.

## 2. New error codes (§12)

`retryable: false` is mandatory on all three; naive retry hits the same
state.

| Code                          | Raised by | When | Surface | Recovery |
| ----------------------------- | --------- | ---- | ------- | -------- |
| `BUDGET_EXHAUSTED`            | runtime   | Lease op attempted while a `cost.budget` counter ≤ 0 (§9.6). Counter reaches zero from `metric{name:"cost.*", unit:<currency>, value:Δ}` events. | Preferred: `tool_result.body.error` so the agent can decide to emit a partial result (§9.6 SHOULD). Fatal alt: `job.error { final_status: "error", code: "BUDGET_EXHAUSTED" }`. | Client must submit a new job with a larger `cost.budget` — no renewal exists. |
| `LEASE_EXPIRED`               | runtime   | Lease op attempted at or after `lease_constraints.expires_at` (§9.5), **or** wall clock reaches `expires_at` while the job is still running. | `tool_result.body.error` for in-flight ops; `job.error { final_status: "error", code: "LEASE_EXPIRED" }` for wall-clock expiry. | Client must cancel and resubmit with a later `expires_at`. |
| `AGENT_VERSION_NOT_AVAILABLE` | runtime   | `job.submit.payload.agent` is `name@version` where the runtime knows `name` but not that `version` (§7.5). | `session.error` (per spec §13.7 example), not `job.error` — no job ever existed. | Client lists agent inventory from welcome's `capabilities.agents` and resubmits with a known version. |

Notes on client-side raising: the client emits **no** `*_EXHAUSTED` /
`*_EXPIRED` error envelopes — these are strictly runtime-emitted. The
client surface for all three is **only** parsing inbound `code` strings
into typed exceptions (`BudgetExhaustedError`, `LeaseExpiredError`,
`AgentVersionNotAvailableError`) and raising them from `handle.done`,
`client.submit()`, or the relevant `tool_result` body. This matches the
TS reference at `packages/core/src/errors.ts`.

## 3. Capability negotiation (§6.2)

`session.hello.payload.capabilities.features` is the client's set;
`session.welcome.payload.capabilities.features` is the runtime's.
Effective set is the intersection. Either peer using a feature outside
the intersection MUST surface `INVALID_REQUEST`.

Canonical feature names — must be string-equal across SDKs because they
ride the wire. From spec §6.2 (one feature per spec subsection):

| Feature flag       | Spec § | Gates                                                                              |
| ------------------ | ------ | ---------------------------------------------------------------------------------- |
| `heartbeat`        | §6.4   | `session.ping` / `session.pong`, `heartbeat_interval_sec`, `HEARTBEAT_LOST` close. |
| `ack`              | §6.5   | `session.ack`, runtime-side early buffer release, back-pressure status events.     |
| `list_jobs`        | §6.6   | `session.list_jobs` / `session.jobs`.                                              |
| `subscribe`        | §7.6   | `job.subscribe` / `job.subscribed` / `job.unsubscribe`.                            |
| `lease_expires_at` | §9.5   | `lease_constraints.expires_at` validation + enforcement, `LEASE_EXPIRED`.          |
| `cost.budget`      | §9.6   | Budget counters, `BUDGET_EXHAUSTED`, runtime-emitted `cost.budget.remaining`.      |
| `progress`         | §8.2   | `progress` event kind + body schema.                                               |
| `result_chunk`     | §8.4   | `result_chunk` event kind + `result_id`/`result_size` on `job.result`.             |
| `agent_versions`   | §7.5   | `name@version` parsing, rich `capabilities.agents` shape, `AGENT_VERSION_NOT_AVAILABLE`. |

Negotiation properties that must be expressed in the type model:

- Features are **independently** negotiable. A runtime offering only
  `heartbeat` is conformant; a client demanding `cost.budget` against
  such a runtime fails closed (refuses to submit cost-bounded jobs).
- Negotiation is **per-session**, not per-process. A client connected to
  two different runtimes may have two different effective sets in
  flight.
- The TS reference exposes both sides via `client.negotiatedFeatures` /
  `client.hasFeature(name)` and the runtime's
  `SessionContext.negotiatedFeatures` / `hasFeature(name)`
  (`typescript-sdk/packages/core/src/version.ts:V1_1_FEATURES`,
  `intersectFeatures`). The Python surface in
  `04-architecture.md` must mirror this — see the helper sketch there.
- The `agents` shape is conditioned on `agent_versions`. v1.1 §6.2
  recommends the rich shape unconditionally, but the client must accept
  both `string[]` and `Array<{name,versions,default?}>` because v1.0
  runtimes still ship the flat form.

## 4. What v1.1 does NOT change

These rows close the diff: any code touching them is unaffected by the
migration and is a candidate for "no v1.1 work, but possibly still
needs v1.0 alignment" in `02-current-audit.md`.

- §4 Transport. WebSocket / stdio / alt transports unchanged.
- §5.1 Envelope shape. Same 8 fields, same `arcp: "1"` constant, same
  unknown-field rule.
- §6.1 Bearer-token auth. No new schemes.
- §6.3 Resume. Token rotates on welcome; `RESUME_WINDOW_EXPIRED`
  unchanged. `session.ack` does **not** alter resume semantics.
- §7.2 Idempotency. Same `(principal, idempotency_key)` window; same
  `DUPLICATE_KEY`.
- §7.3 Lifecycle states. `pending → running → {success | error |
  cancelled | timed_out}`. New error codes plug into the existing
  `error` terminal — no new states.
- §7.4 Cancellation. Subscribers explicitly do NOT inherit cancel
  authority (§7.6).
- §8.1 Event envelope. `payload.kind` / `payload.ts` / `payload.body`
  structure unchanged; v1.1 just reserves two new `kind` values.
- §8.3 Sequence numbers. Session-scoped, gap-free, monotonic. Ping,
  pong, ack are explicitly excluded from the seq space.
- §9.1–§9.3 Capability model and enforcement. The lease itself stays
  immutable at submit; v1.1 adds a separate `lease_constraints` field
  and a separate `cost.budget` namespace, neither of which mutates the
  lease grammar.
- §10 Delegation. Mechanics unchanged. v1.1 §9.4 just adds two subset
  rules (budget remaining; expiry).
- §11 Trace propagation. W3C `traceparent` via
  `extensions["x-vendor.opentelemetry.tracecontext"]` is unchanged; the
  two new span attrs are advisory.
- §12 v1.0 error codes. All twelve survive verbatim; v1.1 only adds
  three.
- §13–§15 Examples, security, IANA. Augmented, not rewritten.

The matter for `02-current-audit.md`: the Python SDK does **not yet** meet
the unchanged-in-v1.1 surface above (it implements draft-01, not draft-02).
That alignment work dominates the migration; v1.1 deltas listed in §1 are
the smaller half of the total scope.
