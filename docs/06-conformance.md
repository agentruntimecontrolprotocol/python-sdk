---
title: "Conformance — ARCP v1.1 (Python)"
sdk: python
spec_sections: ["§4", "§5", "§6", "§7", "§8", "§9", "§10", "§11", "§12", "§13", "§14", "§15"]
order: 6
kind: conformance
---

Status of the ARCP v1.1 normative requirements in this SDK. Status
values are `Implemented` or `Deferred` only. Citations are
`<repo-relative-path>:L<line>` rooted at `src/arcp/`.

## §4 Transports

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §4.1 WebSocket transport                 | Implemented | `arcp/_transport/websocket.py:L18`        |
| §4.2 stdio transport (newline JSON)      | Implemented | `arcp/_transport/stdio.py:L13`            |
| §4.3 In-memory transport (test surface)  | Implemented | `arcp/_transport/in_memory.py:L11`        |
| §4 `Transport` Protocol                  | Implemented | `arcp/_transport/base.py:L13`             |

## §5 Wire format

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §5.1 `Envelope` shape and required fields | Implemented | `arcp/_envelope.py:L30`                   |
| §5.2 ULID id validator                   | Implemented | `arcp/_envelope.py:L20` ; `arcp/_envelope.py:L53` |
| §5.2 W3C `trace_id` validator            | Implemented | `arcp/_envelope.py:L26` ; `arcp/_envelope.py:L60` |
| §5.2 `event_seq` non-negative integer    | Implemented | `arcp/_envelope.py:L71`                   |
| §5.3 Vendor `x-` extension passthrough   | Implemented | `arcp/_extensions.py:L1`                  |
| §5.4 Protocol version `arcp` field       | Implemented | `arcp/_version.py:L5` ; `arcp/_envelope.py:L46` |

## §6 Sessions

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §6.1 Bearer authentication               | Implemented | `arcp/_auth/bearer.py:L26`                |
| §6.1 JWT verifier                        | Implemented | `arcp/_auth/jwt.py:L1`                    |
| §6.2 Capability intersection rule        | Implemented | `arcp/_version.py:L21`                    |
| §6.2 `negotiated_features` exposure (client) | Implemented | `arcp/_client/client.py:L107`         |
| §6.2 `negotiated_features` exposure (runtime) | Implemented | `arcp/_runtime/session.py:L75`        |
| §6.3 `session.hello` / `session.welcome` handshake | Implemented | `arcp/_runtime/server.py:L262` ; `arcp/_client/client.py:L133` |
| §6.3 Resume window enforcement           | Implemented | `arcp/_runtime/server.py:L262`            |
| §6.4 Heartbeat ping / pong               | Implemented | `arcp/_runtime/session.py:L184` ; `arcp/_client/client.py:L187` |
| §6.4 `HEARTBEAT_LOST` on timeout         | Implemented | `arcp/_runtime/session.py:L184`           |
| §6.5 `session.ack` back-pressure         | Implemented | `arcp/_runtime/server.py:L411` ; `arcp/_client/client.py:L435` |
| §6.6 `session.list_jobs` filters / cursor | Implemented | `arcp/_runtime/server.py:L426` ; `arcp/_client/client.py:L354` |
| §6.7 `session.bye` and orderly close     | Implemented | `arcp/_runtime/server.py:L422` ; `arcp/_client/client.py:L454` |

## §7 Jobs

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §7.1 `job.submit` validation             | Implemented | `arcp/_runtime/server.py:L478`            |
| §7.2 `job.accepted` echoes lease         | Implemented | `arcp/_runtime/server.py:L478`            |
| §7.3 `job.cancel` → terminal `CANCELLED` | Implemented | `arcp/_runtime/server.py:L669`            |
| §7.4 Idempotency dedup (in-memory)       | Implemented | `arcp/_runtime/pending.py:L1`             |
| §7.5 `name@version` agent refs           | Implemented | `arcp/_runtime/server.py:L185` ; `arcp/_messages/execution.py:L1` |
| §7.5 `set_default_agent_version`         | Implemented | `arcp/_runtime/server.py:L164`            |
| §7.5 `AGENT_VERSION_NOT_AVAILABLE`       | Implemented | `arcp/_errors.py:L63`                     |
| §7.6 `job.subscribe` / `job.subscribed`  | Implemented | `arcp/_runtime/server.py:L684` ; `arcp/_client/client.py:L376` |
| §7.6 Replay from `from_event_seq`        | Implemented | `arcp/_runtime/server.py:L684`            |

## §8 Job events

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §8.1 Core event kinds (log/thought/status/metric/tool_*) | Implemented | `arcp/_runtime/job.py:L183` |
| §8.2 `progress` event kind               | Implemented | `arcp/_runtime/job.py:L227`               |
| §8.3 Per-session monotonic `event_seq`   | Implemented | `arcp/_runtime/session.py:L81`            |
| §8.4 `result_chunk` writer               | Implemented | `arcp/_runtime/job.py:L259`               |
| §8.4 `collect_chunks` reader             | Implemented | `arcp/_client/handles.py:L70`             |
| §8.4 Inline / chunk mutual exclusion     | Implemented | `arcp/_runtime/job.py:L259`               |
| §8.5 Terminal envelopes (`job.result`, `job.error`) | Implemented | `arcp/_runtime/job.py:L104` ; `arcp/_runtime/job.py:L122` |

## §9 Leases

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §9.1 Lease subset rule on grant          | Implemented | `arcp/_runtime/lease.py:L143`             |
| §9.1 `LEASE_SUBSET_VIOLATION` on authorize | Implemented | `arcp/_runtime/lease.py:L87`            |
| §9.2 Capability namespace validator      | Implemented | `arcp/_runtime/lease.py:L29`              |
| §9.3 Glob target matching                | Implemented | `arcp/_runtime/lease.py:L83`              |
| §9.4 Per-currency budget subset rule     | Implemented | `arcp/_runtime/lease.py:L143`             |
| §9.5 `lease_expires_at` validation       | Implemented | `arcp/_runtime/lease.py:L51`              |
| §9.5 Lease watchdog                      | Implemented | `arcp/_runtime/server.py:L646`            |
| §9.6 `cost.budget` initial snapshot      | Implemented | `arcp/_runtime/lease.py:L115`             |
| §9.6 Per-event budget decrement          | Implemented | `arcp/_runtime/job.py:L68`                |
| §9.6 `BUDGET_EXHAUSTED` on floor         | Implemented | `arcp/_runtime/job.py:L68`                |
| §9.7 `model.use` authorization           | Implemented | `arcp/_runtime/job.py:L285`               |
| §9.8 Provisioned credential interface    | Implemented | `arcp/_runtime/credentials.py:L1`         |
| §9.8 Issue credentials on job acceptance | Implemented | `arcp/_runtime/_handlers.py:L158`         |
| §9.8 Revoke credentials on terminal state | Implemented | `arcp/_runtime/_job_runner.py:L145`      |

## §10 Delegation

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §10.1 Strict-subset child lease          | Implemented | `arcp/_runtime/lease.py:L182`             |
| §10.2 `parent_job_id` propagation        | Implemented | `arcp/_client/client.py:L293`             |
| §10.3 `trace_id` propagation             | Implemented | `arcp/_client/client.py:L293`             |

## §11 Trace propagation

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §11 W3C trace context propagation        | Implemented | `arcp/middleware/otel.py:L95`             |
| §11 v1.1 span attributes                 | Implemented | `arcp/middleware/otel.py:L16`             |

## §12 Error taxonomy

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §12 15 typed exceptions                  | Implemented | `arcp/_errors.py:L8`                      |
| §12 `error_class_for(code)` lookup       | Implemented | `arcp/_errors.py:L138`                    |
| §12 `error_from_payload(payload)`        | Implemented | `arcp/_errors.py:L143`                    |
| §12 v1.1 codes (`HEARTBEAT_LOST`, `LEASE_EXPIRED`, `BUDGET_EXHAUSTED`, `AGENT_VERSION_NOT_AVAILABLE`) | Implemented | `arcp/_errors.py:L83` ; `arcp/_errors.py:L88` ; `arcp/_errors.py:L93` ; `arcp/_errors.py:L63` |

## §13 Examples

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §13 21 reference example programs        | Implemented | `examples/`                               |
| §13.7 Versioned agent example            | Implemented | `examples/agent_versions/`                |

## §14 Security

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §14 Per-chunk size cap on `result_chunk` | Implemented | `arcp/_runtime/job.py:L294`               |
| §14 Bearer-token transport gate          | Implemented | `arcp/_auth/bearer.py:L26`                |
| §14 ASGI host allowlist                  | Implemented | `arcp/middleware/asgi.py:L65`             |

## §15 IANA

| Requirement                              | Status      | Location                                  |
| ---------------------------------------- | ----------- | ----------------------------------------- |
| §15 Protocol version constant            | Implemented | `arcp/_version.py:L5`                     |
| §15 v1.1 feature-flag vocabulary         | Implemented | `arcp/_version.py:L8`                     |

## Intentional deferrals

| Item                                     | Status   | Reason                                                                  |
| ---------------------------------------- | -------- | ----------------------------------------------------------------------- |
| Persistent idempotency store             | Deferred | In-memory only; durability is left to host integrations.                |
| Client-side proactive heartbeat ping     | Deferred | Client replies only; symmetric pinger not shipped this release.         |
| Sandboxed lease enforcement              | Deferred | `validate_lease_op` is the SDK seam; agents call it.                    |
| `msgspec` for hot-path validation        | Deferred | pydantic v2 picked uniformly across the workspace.                      |
