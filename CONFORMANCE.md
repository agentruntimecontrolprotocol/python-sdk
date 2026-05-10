# ARCP v1.0 Conformance Statement — `arcp-py` v0.1.0

This document is the honest mapping between the RFC sections in
`RFC-0001-v2.md` and what this implementation supports. Each row is one of:

- **implemented** — the section is implemented and exercised by tests.
- **partial** — the section is implemented for the v0.1 in-scope subset; the
  out-of-scope portion is explicitly deferred and stubbed.
- **deferred** — the section is intentionally not implemented in v0.1 and
  raises `UNIMPLEMENTED` (or equivalent) at the appropriate boundary.

| Section | Title                                | Status        | Notes                                                                                  |
| ------- | ------------------------------------ | ------------- | -------------------------------------------------------------------------------------- |
| §1–§5   | Goals, terminology, principles, arch | implemented   | Architecture matches PLAN.md; observer / active-client roles supported, peer runtimes deferred. |
| §6.1    | Envelope (full field set)            | implemented   | All §6.1.1 fields present; round-trip preserves every field.                           |
| §6.2    | Message types                        | implemented   | Every type listed in §6.2 is registered. Some are stub payloads (see §10.6, §14, §20). |
| §6.3    | Command/result/event flow            | implemented   | `tool.invoke` → `job.accepted` → `job.started` → progress/streams → terminal event.    |
| §6.4    | Delivery semantics                   | implemented   | Transport `id` deduplication; logical `idempotency_key` via SQLite store.              |
| §6.5    | Priority & QoS                       | partial       | `priority` field carried through; per-priority scheduling not exercised in v0.1.       |
| §7      | Capability negotiation               | implemented   | Required-but-unsupported → `session.rejected` `UNIMPLEMENTED`; intersection performed. |
| §8.1    | Session establishment                | implemented   | Four-step handshake; pre-acceptance non-handshake messages drop + `session.unauthenticated`. |
| §8.2    | Credentials                          | partial       | `bearer`, `signed_jwt`, `none` supported. `mtls`, `oauth2` deferred → `UNIMPLEMENTED`. |
| §8.3    | Runtime identity                     | implemented   | Identity emitted on `session.accepted`.                                                |
| §8.4    | Re-authentication                    | partial       | `session.refresh` plumbed; auto-eviction-on-deadline deferred to v0.2.                 |
| §8.5    | Eviction                             | partial       | `session.evicted` envelope supported; idle / quota policies are runtime-config concerns. |
| §9      | Sessions (stateless / stateful)      | partial       | Stateless and stateful supported; durable session resume only via §19 message-id resume. |
| §10.1   | Durable jobs                         | implemented   | Retries left to tool implementations; heartbeats, cancellation, progress in core.      |
| §10.2   | Job state machine                    | implemented   | All eight states modeled; `paused` is reachable via FSM but no public driver in v0.1.  |
| §10.3   | Heartbeats                           | implemented   | Watchdog with configurable interval and miss-threshold; `HEARTBEAT_LOST` on miss.      |
| §10.4   | Cancellation                         | implemented   | Cooperative `cancel.accepted`; deadline elapse → hard kill + `ABORTED`.                |
| §10.5   | Interrupts                           | partial       | Plumbing in place via `JobContext.request_human_input`; explicit `interrupt` envelope handler stubbed. |
| §10.6   | Scheduled jobs                       | deferred      | `job.schedule` returns `UNIMPLEMENTED`. RRULE / `at` / `after` not parsed.             |
| §11.1   | Stream kinds                         | implemented   | `text`, `event`, `log`, `metric`, `thought` supported; `binary` via base64 only.       |
| §11.2   | Backpressure                         | partial       | Receiver-rate `desired_rate_per_second` honored; envelope-shed prioritization deferred. |
| §11.3   | Binary encoding                      | partial       | In-envelope base64 supported; sidecar binary frames deferred.                          |
| §11.4   | Reasoning streams                    | implemented   | `kind: thought` payloads carry `role` / `content` / `redacted`.                        |
| §12.1   | Human input request/response         | implemented   | Schema validation runs against `response_schema`.                                      |
| §12.2   | Choice request/response              | implemented   | `choice_id` validated against offered options.                                         |
| §12.3   | Provenance & multi-channel           | partial       | First-response-wins; quorum and per-channel cancellation propagation deferred.         |
| §12.4   | Expiration                           | implemented   | Default-application or `human.input.cancelled` on deadline.                            |
| §13.1   | Subscribe                            | implemented   | `subscribe` / `subscribe.accepted` / `subscribe.event`.                                |
| §13.2   | Filtering                            | implemented   | All five filter dimensions; AND across, OR within.                                     |
| §13.3   | Backfill                             | implemented   | Ordered replay then synthetic `subscription.backfill_complete` boundary marker.        |
| §13.4   | Termination                          | implemented   | Both `unsubscribe` (client-driven) and `subscribe.closed` (runtime-driven).            |
| §14     | Multi-agent coordination             | deferred      | `agent.delegate` / `agent.handoff` registered as types but `UNIMPLEMENTED` at dispatch. |
| §15.1   | Permission model                     | implemented   | Free-form permission strings, opaque to runtime.                                       |
| §15.2   | Sandboxing                           | partial       | Delegated to tool implementations; runtime does not constrain.                         |
| §15.3   | Trust levels                         | partial       | Field-level support; not enforced in v0.1.                                             |
| §15.4   | Permission challenge flow            | implemented   | `permission.request` / `permission.grant` / `permission.deny` round-trip.              |
| §15.5   | Lease lifecycle                      | implemented   | `lease.granted` / `lease.extended` / `lease.refresh` / `lease.revoked`.                |
| §15.6   | Trust elevation                      | deferred      | `trust.elevate.*` synthetic permissions return `UNIMPLEMENTED`.                        |
| §16.1   | Artifact references                  | implemented   | `artifact.ref` payload shape per §16.1.                                                |
| §16.2   | Storage and retrieval                | partial       | Inline base64 only; redirect URI deferred.                                             |
| §16.3   | Lifecycle / retention                | partial       | `expires_at` honored; periodic sweep available; no eager GC daemon by default.         |
| §17.1   | Tracing                              | partial       | `trace_id` / `span_id` / `parent_span_id` carried; no OTel exporter.                   |
| §17.2   | Structured logs                      | implemented   | `log` envelope with full level set.                                                    |
| §17.3   | Metrics                              | implemented   | `metric` envelope; standard metric names enum exposed.                                 |
| §18     | Error model                          | implemented   | Full canonical taxonomy; `is_retryable_default()` aligned with §18.3.                  |
| §19     | Resumability                         | partial       | `after_message_id` resume implemented; `checkpoint_id` resume returns `UNIMPLEMENTED`. |
| §20     | MCP compatibility                    | deferred      | Not integrated; modeling decisions consistent with the recommendation.                 |
| §21.1   | Extension naming                     | implemented   | `arcpx.<vendor>.<name>.v<n>` and reverse-DNS validated.                                |
| §21.2   | Negotiation                          | implemented   | Capabilities-driven advertisement.                                                     |
| §21.3   | Unknown message handling             | implemented   | Core unknown → `UNIMPLEMENTED`; namespaced + `optional: true` → silent drop.           |
| §21.4   | Promotion to core                    | n/a           | No extensions promoted in v0.1.                                                        |
| §22     | Reference transports                 | partial       | WebSocket and stdio implemented; HTTP/2 and QUIC deferred.                             |
| §23–§28 | Examples / future work               | n/a           | See `examples/` and `docs`.                                                            |

## Open RFC Ambiguities (PLAN.md §4)

The PLAN documents twelve open questions and the chosen interpretation. Key
items: §11.1 unknown stream kinds → treat as `event`; §13.2 authorization →
single principal per session unless principal is `arcp.observer.all`; §19
retention → `DATA_LOSS` outside event-log retention horizon.

## Out-of-Scope Tests

These integration tests intentionally do not exist in v0.1 and are tracked
for v0.2:

- mTLS / OAuth2 handshake.
- Sidecar binary stream frames.
- Scheduled jobs (`job.schedule.at|every|after`).
- Multi-agent delegation/handoff.
- Trust elevation via `trust.elevate.*`.
- Checkpoint-based resume.
- Quorum HITL response policies.
