# Conformance

This page records which sections of the [ARCP v1.1 specification](https://arcp.dev/spec/v1.1) are implemented by the Python SDK, and points to the source that implements each requirement.

## Conformance matrix

| Spec section | Title | Status | Source |
|---|---|---|---|
| §4 | Versioning | ✅ Full | `arcp/_version.py` |
| §5 | Transport framing | ✅ Full | `arcp/_transport/` |
| §6 | Sessions | ✅ Full | `arcp/runtime/session.py` |
| §6.1 | Authentication — Bearer | ✅ Full | `arcp/runtime/auth.py` |
| §6.1 | Authentication — custom verifier | ✅ Full | `arcp/runtime/auth.py` |
| §6.2 | Agent versions | ✅ Full | `arcp/runtime/registry.py` |
| §6.3 | Stream resume | ✅ Full | `arcp/runtime/resume.py` |
| §7 | Jobs | ✅ Full | `arcp/runtime/job_runner.py` |
| §7.1 | Idempotency keys | ✅ Full | `arcp/runtime/idempotency.py` |
| §7.2 | Job cancellation | ✅ Full | `arcp/runtime/job_runner.py` |
| §8 | Job events | ✅ Full | `arcp/_envelope.py` |
| §8.1 | `job.queued` | ✅ Full | `arcp/_envelope.py` |
| §8.2 | `job.started` | ✅ Full | `arcp/_envelope.py` |
| §8.3 | `job.log` | ✅ Full | `arcp/runtime/context.py` |
| §8.4 | `job.progress` | ✅ Full | `arcp/runtime/context.py` |
| §8.5 | `job.result_chunk` | ✅ Full | `arcp/runtime/context.py` |
| §8.6 | `job.completed` | ✅ Full | `arcp/runtime/job_runner.py` |
| §8.7 | `job.failed` | ✅ Full | `arcp/runtime/job_runner.py` |
| §8.8 | `job.cancelled` | ✅ Full | `arcp/runtime/job_runner.py` |
| §8.9 | `job.heartbeat` | ✅ Full | `arcp/runtime/heartbeat.py` |
| §9 | Leases | ✅ Full | `arcp/runtime/lease.py` |
| §9.1 | Cost budgets | ✅ Full | `arcp/runtime/lease.py` |
| §9.2 | Time budgets (`expires_in_s`) | ✅ Full | `arcp/runtime/lease.py` |
| §9.3 | `expires_at` (absolute timestamp) | ✅ Full | `arcp/runtime/lease.py` |
| §10 | Delegation | ✅ Full | `arcp/runtime/delegation.py` |
| §11 | Observability | ✅ Full | `arcp/middleware/otel.py` |
| §12 | Errors | ✅ Full | `arcp/_errors.py` |
| §13 | Capability negotiation | ✅ Full | `arcp/runtime/capabilities.py` |
| §14 | List jobs | ✅ Full | `arcp/runtime/job_store.py` |
| §15 | Vendor extensions | ✅ Full | `arcp/_extensions.py` |

## Notes

### §6.3 Stream resume

Resume tokens are opaque strings returned in the `job.started` event. Pass the token in a new `submit()` call with `resume_token=...` to replay missed events from that point forward.

### §9.3 `expires_at`

`expires_at` accepts an ISO 8601 datetime string (UTC). The runtime converts it to `expires_in_s` for internal tracking.

### §10 Delegation

Delegation tokens are signed JWTs. The SDK provides `runtime.create_delegation_token(principal, scopes)` and verifies incoming tokens automatically.

### §15 Vendor extensions

Any `x-*` key in a submit payload or event payload is passed through without modification. Use `arcp._extensions.get_extension(event, "x-my-field")` to read them safely.
