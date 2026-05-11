# ARCP Examples

Fourteen single-purpose codebases, each named for the protocol
primitive it demonstrates.

> **Illustrative, not runnable.** Each example imports from the
> in-repo `arcp` package as if it were a published `arcp>=1.0,<2.0`
> SDK. Setup boilerplate (transport URL, identity, auth) is elided
> with `ARCPClient(...)`. LLM and framework calls live in tiny stub
> files (`agents.py`, `steps.py`, `synth.py`, …) so the protocol
> code in `main.py` is what you read.

## The fourteen

| Directory | Demonstrates | Spec |
|---|---|---|
| [`subscriptions/`](./subscriptions) | Three Observer clients on one session, three filters, three sinks. | §5, §13 |
| [`leases/`](./leases) | Lease-gated shell agent. Read leases coarse, write leases scoped. | §15.4–§15.5 |
| [`lease_revocation/`](./lease_revocation) | Per-table leases with `lease.revoked` / `lease.extended` mid-flight. | §15.5 |
| [`permission_challenge/`](./permission_challenge) | Two-party permission challenge — generator asks, reviewer holds veto. | §15.4, §6.4 |
| [`delegation/`](./delegation) | `agent.delegate` fan-out + `JobMux` to demux events by `job_id`. | §14, §6.4 |
| [`handoff/`](./handoff) | `agent.handoff` with transcript packed as an artifact, runtime fingerprint pinned. | §14, §16, §8.3 |
| [`heartbeats/`](./heartbeats) | Worker federation; heartbeat-loss reroute via `idempotency_key`. | §10.3, §6.4 |
| [`capability_negotiation/`](./capability_negotiation) | Capability-driven peer routing; standard `cost.usd` rollups. | §7, §17.3.1, §18.3 |
| [`resumability/`](./resumability) | **Actually crash and resume.** `os._exit` mid-flight; second invocation picks up at the next step. | §10, §19, §6.4 |
| [`reasoning_streams/`](./reasoning_streams) | `kind: thought` stream + a peer runtime that subscribes and delegates critiques back. | §11.4, §13, §14 |
| [`extensions/`](./extensions) | Custom `arcpx.sdr.*.v1` extension namespace with correct unknown-message handling. | §21 |
| [`human_input/`](./human_input) | `human.input.request` fanned across phone/email/Slack; first-wins resolution. | §12 |
| [`cancellation/`](./cancellation) | Cooperative `cancel` (terminate) vs `interrupt` (pause and ask). | §10.4–§10.5 |
| [`mcp/`](./mcp) | ARCP runtime fronting an MCP server: `tool.invoke` → MCP `call_tool`. | §20 |

## Conventions

- Python 3.12+, type-annotated, ruff-clean at line length 80.
- `examples/ruff.toml` overrides the repo's default 100 just for
  this directory.
- Each example is one `main.py` (the protocol code) + 0–2 stub
  modules named for what they elide (`agents.py`, `steps.py`,
  `cheap.py`, `synth.py`, `work.py`, `channels.py`, `sql.py`,
  `upstream.py`).
- `ARCPClient(...)` literally — transport, identity, and auth
  blocks are setup noise, not the point.
- Envelopes match RFC-0001 v2 exactly. Custom message types follow
  §21.1 `arcpx.<domain>.<name>.v<n>` naming.

## What's where in the SDK

- `arcp.ARCPClient` — handshake driver. Use `client.envelope(type,
  payload=..., **kwargs)` to mint envelopes with `id` and
  `session_id` filled in.
- `arcp.Envelope`, `arcp.ErrorCode`, `arcp.ARCPError` — wire
  primitives.
- `arcp.new_message_id()` — for runtime-side code that builds
  envelopes outside an `ARCPClient`.
- `arcp.transport.websocket` — most common transport.
- `arcp.store.eventlog` — SQLite schema reused by `subscriptions`.

## Reading order

For a brisk tour: `subscriptions`, `leases`, `delegation`,
`resumability` (this one actually crashes and recovers),
`cancellation`, `extensions`, `mcp_compat`. These seven exercise
the bulk of the protocol.

## Spec ambiguities surfaced

See [`LEARNED.md`](./LEARNED.md).
