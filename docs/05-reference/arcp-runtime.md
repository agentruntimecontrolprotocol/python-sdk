---
title: "arcp.runtime"
sdk: python
order: 2
kind: reference
---

Module `arcp.runtime`. Hosts agents, accepts transports, enforces
leases, persists events.

## Symbols

| Name                       | Kind     | Summary                                                                |
| -------------------------- | -------- | ---------------------------------------------------------------------- |
| `ARCPRuntime`              | class    | Runtime state machine: handshake, dispatch, agent registry.            |
| `Agent`                    | alias    | `Callable[[Any, JobContext], Awaitable[Any]]`.                         |
| `Job`                      | class    | Runtime-side per-job state.                                            |
| `JobContext`               | class    | Per-job API surface passed to agent bodies (see [job-context.md](job-context.md)). |
| `SessionContext`           | class    | Per-session state: negotiated features, event seq, subscribers.        |
| `SessionState`             | class    | Internal session state container.                                      |
| `AuthorizationContext`     | class    | Inputs to `JobAuthorizationPolicy` for submit-time gating.             |
| `JobAuthorizationPolicy`   | alias    | `Callable[[AuthorizationContext], bool]`.                              |
| `BearerVerifier`           | proto    | Token verification interface.                                          |
| `Identity`                 | class    | `principal: str` and optional claims, returned by the verifier.        |
| `StaticBearerVerifier`     | class    | Map of token → principal for tests and the CLI demo.                   |
| `JWTVerifier`              | class    | JWT signature verifier.                                                |
| `EventLog`                 | proto    | Append-only event store interface.                                     |
| `InMemoryEventLog`         | class    | Default in-process event log.                                          |
| `SqliteEventLog`           | class    | SQLite-backed log; powers `arcp replay`.                               |
| `validate_lease_shape`     | function | Structural lease check.                                                |
| `validate_lease_constraints`| function | `expires_at` / `cost.budget` constraint validation.                   |
| `validate_lease_op`        | function | Per-op gate called from `JobContext.authorize`.                        |
| `is_lease_subset`          | function | Subset test for delegation.                                            |
| `assert_lease_subset`      | function | Raises `LeaseSubsetViolationError` on failure.                         |
| `initial_budget_from_lease`| function | Decimal budget snapshot from a granted lease.                          |

## ARCPRuntime

```python
class ARCPRuntime:
    def __init__(
        self,
        *,
        runtime: RuntimeInfo,
        bearer: BearerVerifier,
        event_log: EventLog | None = None,
        capabilities: Capabilities | None = None,
        features: tuple[str, ...] | None = None,
        heartbeat_interval_sec: float | None = None,
        heartbeat_timeout_sec: float | None = None,
        authorization_policy: JobAuthorizationPolicy | None = None,
        ack_window_max: int | None = None,
        logger: Any = None,
    ) -> None: ...

    def register_agent(self, name: str, fn: Agent) -> Self: ...
    def register_agent_version(self, name: str, version: str, fn: Agent) -> Self: ...
    def set_default_agent_version(self, name: str, version: str) -> Self: ...
    def agent_inventory(self) -> tuple[AgentInventoryEntry, ...]: ...
    async def accept(self, transport: Transport) -> None: ...
    async def close(self) -> None: ...
```

`accept(transport)` drives one session end-to-end: handshake, dispatch
loop, event log fan-out, heartbeat (if negotiated), and orderly close
on `session.bye` or transport failure. Concurrent calls on different
transports are independent.

**Raises**: never raises into the caller of `accept`; protocol
violations surface as `session.error` envelopes on the wire and the
transport is closed.

## See also

- Reference: [`job-context.md`](job-context.md), [`transport.md`](transport.md), [`errors.md`](errors.md).
- Features: [`../03-features/heartbeats.md`](../03-features/heartbeats.md), [`../03-features/agent-versions.md`](../03-features/agent-versions.md).
- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §§6–10.
