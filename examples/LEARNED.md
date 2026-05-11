# LEARNED

Notes from writing the fourteen examples against RFC-0001 v2. Items
roughly ordered by how often they bit. Some are real spec gaps;
some are friction in expressing the spec in Python.

## Spec gaps and ambiguities

### 1. `extensions.optional` is convention, not schema

§21.3 says receivers MUST nack unknowns *unless* the sender marked
the message `extensions.optional: true`. The envelope schema
documents `extensions` as a free-form `dict[str, Any]` but never
reserves the `optional` key. Two examples (`extensions`,
`reasoning_streams`) lean on this convention. Spec should reserve
the key or define a typed envelope flag.

### 2. Backfill terminator envelope is unspecified

§13.3 prescribes "a synthetic `subscription.backfill_complete`
marker" but doesn't pin the envelope type. We adopt
`event.emit` with `payload.name = "subscription.backfill_complete"`.
`resumability` relies on this to know when replay ends.

### 3. Lease `resource` grammar is free-form

§15.5 defines `resource` as a string; the examples drift to
different conventions:

- `leases`: `host:<host>/<binary>/<argv1>`
- `lease_revocation`: `table:<schema>.<name>`
- `permission_challenge`: `ticket:<id>/<patch_sha>`

All reasonable. None interoperate. A loose grammar
(`<scheme>:<path>`) would help observability sinks slice by
resource type.

### 4. Handoff context transfer is gestural

§14 mentions `shared_memory_ref` in an example payload but
`AgentHandoffPayload` only models `target_runtime`, `job_id`,
`session_id`. `handoff` packs the conversation into an
`artifact.put` and references it from a non-modeled
`shared_memory_ref` field. Either formalize the field or specify
that handoff context flows exclusively as artifacts.

### 5. Capability extensions need a value type

§7 lets capabilities carry arbitrary additional fields (the SDK's
`Capabilities` model has `extra="allow"`), but §21 only addresses
extension *messages*, not extension *capability values*.
`capability_negotiation` advertises `arcpx.market.cost_per_mtok.v1` as
a numeric capability value. The spec should explicitly cover this.

### 6. Cooperative cancel contract is loose

§10.4 says "the runtime SHOULD drive the target to a clean
checkpoint within `deadline_ms` before terminating" but leaves
escalation to "MAY hard-kill". Implementations will diverge on
whether `deadline_ms` resets on each progress event or is absolute.
`cancellation` documents the contract but can't enforce it.

### 7. `permission.request` reply envelope is implicit

The §15.4 example shows `permission.grant` / `permission.deny` but
the spec also implies `lease.granted` follows on grant. Whether the
*reply* to a `permission.request` is `permission.grant` (with
`lease.granted` arriving separately) or `lease.granted` directly is
implementation-defined. The SDK collapses these; `leases`,
`lease_revocation`, and `permission_challenge` all treat
`lease.granted` as the success reply. Worth pinning.

### 8. Mirror role is between Observer and Peer

§5 defines Observers as "subscriptions only; never command" and
Peer Runtimes as the federation/`agent.delegate` party. The mirror
in `reasoning_streams` does both: it subscribes to the primary's
thoughts AND emits `agent.delegate` carrying critiques back into
the primary's session. We classify it as a peer runtime
(`trust_level: trusted`); §5 is silent on this hybrid.

## Python expression friction

### 9. `client.events()` is single-consumer

`ARCPClient.events()` exposes a single shared queue. Multiple
coroutines iterating it in parallel starve each other. `delegation`
ships a `JobMux` that owns the iterator and demuxes by `job_id`.
The SDK should ship something like this, or at least document the
constraint.

### 10. Boilerplate before `client.envelope()` was painful

Pre-helper, every example had its own `_msg_id()` and threaded
`session_id` by hand. We added `ARCPClient.envelope(type, ...)` to
the SDK partway through; it cut ~6 LOC per call site. If the SDK
hadn't grown this method these examples would be 30% noise.

### 11. Reasoning streams want stronger typing

`stream.chunk.payload` is `extra="allow"` because chunk shape
varies by `kind`. For `kind: thought` we end up with a hand-rolled
contract (`role: assistant_thought`, `content: str`,
`redacted: bool`). A nested model per kind would be friendlier to
write tests against.

### 12. `idempotency_key` retention horizon is unstated

§6.4 says runtimes "SHOULD persist `(session_principal,
idempotency_key)` for at least the lease horizon of the operation",
but `resumability` and `heartbeats` use
`idempotency_key` for things that aren't lease-scoped (workflow
steps, worker re-dispatch). A "MUST persist for at least the
declared retention window" clause would settle this.

### 13. Unbounded `asyncio.create_task` for runtime-of-process tasks

Several examples spawn supervisor / drain / route tasks that live
for `main()`'s whole lifetime. Ruff's RUF006 wants the task stored
to a name; we suppress because storing in a never-read variable is
weirder than just letting the task run. This isn't an ARCP issue —
it's a Python-async one — but writing this many event loops back to
back made it loud.

## What I'd change in the spec

- Reserve `extensions.optional: bool` in §21.3.
- Pin the backfill terminator envelope in §13.3.
- Sketch a loose `<scheme>:<path>` lease `resource` grammar.
- Either model `shared_memory_ref` on `AgentHandoffPayload` or
  state the artifact-only convention in §14.
- Cover capability extension *values* in §21.
- Clarify the `permission.request` → `lease.granted` collapse in
  §15.4 / §15.5.
- Document the hybrid Observer/Peer role exemplified by
  `reasoning_streams`.
- Add a non-normative note in Appendix B that the canonical event
  surface is single-consumer (or recommend a JobMux pattern).
