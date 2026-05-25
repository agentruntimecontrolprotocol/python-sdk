# Conformance

This page records which sections of the [ARCP v1.1 specification](https://arcp.dev/spec/v1.1) are implemented by the Python SDK, and points to the source that implements each requirement. Every source path listed below exists in this repository under `src/arcp/`.

## Conformance matrix

| Spec section | Title | Status | Source |
|---|---|---|---|
| §4 | Versioning / protocol constant | Full | `src/arcp/_version.py`, `src/arcp/_envelope.py` |
| §5.1 | Envelope shape (8 fields) | Full | `src/arcp/_envelope.py` |
| §5.2 | Wire framing (WebSocket / stdio / memory) | Full | `src/arcp/_transport/` |
| §6.1 | `session.hello` / `session.welcome` | Full | `src/arcp/_runtime/_handshake.py` |
| §6.1 | Authentication — bearer (static + custom) | Full | `src/arcp/_auth/bearer.py` |
| §6.1 | Authentication — JWT / JWKS | Full | `src/arcp/_auth/jwt.py` |
| §6.2 | Capability / feature negotiation | Full | `src/arcp/_runtime/_handshake.py`, `src/arcp/_version.py` |
| §6.3 | Session resume (`hello.resume`) | Full | `src/arcp/_runtime/_handshake.py`, `src/arcp/_store/eventlog.py` |
| §6.4 | Heartbeat / liveness | Full | `src/arcp/_runtime/session.py` (`heartbeat_loop`) |
| §6.5 | Ack backpressure | Full | `src/arcp/_runtime/_handlers.py` (`handle_ack`) |
| §6.6 | `session.bye` / orderly close | Full | `src/arcp/_runtime/_handlers.py` (`handle_bye`) |
| §7.1 | `job.submit` / `job.accepted` | Full | `src/arcp/_runtime/_handlers.py` (`handle_submit`) |
| §7.2 | Idempotency keys (accept + terminal replay) | Full | `src/arcp/_store/idempotency.py`, `src/arcp/_runtime/_handlers.py` |
| §7.3 | Agent versions (`agent@version` selection) | Full | `src/arcp/_runtime/server.py` (`_resolve_agent`) |
| §7.4 | `job.cancel` (submitter-only) | Full | `src/arcp/_runtime/_handlers.py` (`handle_cancel`) |
| §7.5 | `session.list_jobs` (filter + cursor) | Full | `src/arcp/_runtime/_handler_list_jobs.py` |
| §7.6 | `job.subscribe` / `job.unsubscribe` | Full | `src/arcp/_runtime/_handlers.py` |
| §8.1 | `log`, `thought`, `status` events | Full | `src/arcp/_runtime/job.py` (`JobContext`) |
| §8.2 | `metric`, `tool_call`, `tool_result` | Full | `src/arcp/_runtime/job.py`, `src/arcp/_messages/event_bodies.py` |
| §8.3 | `progress` events | Full | `src/arcp/_runtime/job.py` (`JobContext.progress`) |
| §8.4 | `result_chunk` + streamed `job.result` | Full | `src/arcp/_runtime/result_stream.py` |
| §8.5 | Terminal `job.result` / `job.error` | Full | `src/arcp/_runtime/job.py` (`Job.emit_result`, `Job.emit_error`) |
| §9.1 | Lease shape + glob validation | Full | `src/arcp/_runtime/lease.py` (`validate_lease_shape`) |
| §9.2 | Cost budgets (Decimal arithmetic) | Full | `src/arcp/_runtime/lease.py`, `src/arcp/_runtime/job.py` |
| §9.3 | Lease constraints (`expires_at`, `model.use`) | Full | `src/arcp/_runtime/lease.py` (`validate_lease_constraints`) |
| §9.4 | Lease watchdog (auto-expiry) | Full | `src/arcp/_runtime/_job_runner.py` (`_lease_watchdog`) |
| §9.5 | Sublease shape rules for delegation | Full | `src/arcp/_runtime/lease.py` (`assert_lease_subset`) |
| §10 | Provisioned credentials + revocation | Full | `src/arcp/_runtime/credentials.py`, `src/arcp/_runtime/_handlers.py` |
| §11 | Observability — OTel transport wrapper | Full | `src/arcp/middleware/otel.py` |
| §12 | Typed errors + `session.error` payload | Full | `src/arcp/_errors.py` |
| §13 | Vendor extensions (`x-*` passthrough) | Full | `src/arcp/_extensions.py` |
| §14 | Authorization defaults + policy seam | Full | `src/arcp/_runtime/server.py` (`AuthorizationContext`) |

## Notes

### §6.3 Stream resume

`SessionResume` carries `(session_id, resume_token, last_event_seq)` in a
`session.hello`. The runtime keeps a per-session resume record for
`resume_window_sec` after disconnect, validates the resume token + principal
on rejoin, reuses the original `session_id`, rotates the resume token, and
replays buffered envelopes from the event log past `last_event_seq`. Jobs do
not run across the disconnect boundary; only history is replayed.

### §6.5 Ack backpressure

`session.ack` releases acked prefixes from the in-memory or SQLite event log
synchronously inside the dispatch loop (per-session serialized).
`AutoAckOptions` on the client coalesces acks by event count and interval.

### §7.2 Idempotency

A duplicate `job.submit` with the same `(principal, idempotency_key)`
replays the original `job.accepted` AND, if the original job has reached a
terminal state, also replays the stored `job.result` or `job.error`. This
prevents the duplicate `JobHandle` from hanging on `await handle.done`.

### §10 Provisioned credentials

Credentials are issued via a pluggable `CredentialProvisioner`, recorded in
a durable `RevocationLog`, attached to `job.accepted`, and revoked when the
job ends. Credential rotation is exposed via `JobContext.rotate_credential`.

### §13 Vendor extensions

Any `x-vendor.*` key in an envelope payload or event body is passed through
without modification — every pydantic payload model in `arcp._messages.*`
uses `model_config = ConfigDict(extra="allow")`. Validate keys with
`arcp._extensions.validate_extension_key("x-vendor.my-field")` before sending
to ensure forward compatibility.
