# Conformance

This page records which sections of the [ARCP v1.1 specification](https://arcp.dev/spec/v1.1) are implemented by the Python SDK, and points to the source that implements each requirement.

## Conformance matrix

| Spec section | Title | Status | Source |
|---|---|---|---|
| §4 | Versioning | ✅ Full | `src/arcp/_version.py` |
| §5 | Transport framing | ✅ Full | `src/arcp/_transport/` |
| §6 | Sessions | ✅ Full | `src/arcp/_runtime/session.py` |
| §6.1 | Authentication — Bearer | ✅ Full | `src/arcp/_auth/bearer.py` |
| §6.1 | Authentication — custom verifier | ✅ Full | `src/arcp/_auth/jwt.py` |
| §6.2 | Agent versions | ✅ Full | `src/arcp/_runtime/server.py` |
| §6.3 | Stream resume | ✅ Full | `src/arcp/_runtime/session.py` |
| §7 | Jobs | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §7.1 | Idempotency keys | ✅ Full | `src/arcp/_store/idempotency.py` |
| §7.2 | Job cancellation | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §8 | Job events | ✅ Full | `src/arcp/_envelope.py` |
| §8.1 | `job.queued` | ✅ Full | `src/arcp/_envelope.py` |
| §8.2 | `job.started` | ✅ Full | `src/arcp/_envelope.py` |
| §8.3 | `job.log` | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §8.4 | `job.progress` | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §8.5 | `job.result_chunk` | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §8.6 | `job.completed` | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §8.7 | `job.failed` | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §8.8 | `job.cancelled` | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §8.9 | `job.heartbeat` | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §9 | Leases | ✅ Full | `src/arcp/_runtime/lease.py` |
| §9.1 | Cost budgets | ✅ Full | `src/arcp/_runtime/lease.py` |
| §9.2 | Time budgets (`expires_in_s`) | ✅ Full | `src/arcp/_runtime/lease.py` |
| §9.3 | `expires_at` (absolute timestamp) | ✅ Full | `src/arcp/_runtime/lease.py` |
| §10 | Delegation | ✅ Full | `src/arcp/_runtime/_handlers.py` |
| §11 | Observability | ✅ Full | `src/arcp/middleware/otel.py` |
| §12 | Errors | ✅ Full | `src/arcp/_errors.py` |
| §13 | Capability negotiation | ✅ Full | `src/arcp/_runtime/server.py` |
| §14 | List jobs | ✅ Full | `src/arcp/_runtime/_handler_list_jobs.py` |
| §15 | Vendor extensions | ✅ Full | `src/arcp/_extensions.py` |

## Notes

### §6.3 Stream resume

Resume remains session-scoped in the current implementation. Treat the older
`resume_token` submit flow as deferred until the runtime exposes it publicly.

### §9.3 `expires_at`

`expires_at` accepts an ISO 8601 datetime string (UTC). The runtime converts it to `expires_in_s` for internal tracking.

### §10 Delegation

Delegation tokens are signed JWTs. The SDK provides `runtime.create_delegation_token(principal, scopes)` and verifies incoming tokens automatically.

### §15 Vendor extensions

Any `x-*` key in a submit payload or event payload is passed through without modification. Use `arcp._extensions.get_extension(event, "x-my-field")` to read them safely.
