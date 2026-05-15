---
title: "arcp.client"
sdk: python
order: 1
kind: reference
---

Module `arcp.client`. Public client surface: connect to a runtime,
submit jobs, subscribe to other sessions' jobs, list inventory, send
acks, and close cleanly.

## Symbols

| Name             | Kind  | Summary                                                          |
| ---------------- | ----- | ---------------------------------------------------------------- |
| `ARCPClient`     | class | Async client; one per session.                                   |
| `AutoAckOptions` | class | Configuration for periodic auto-ack when `ack` is negotiated.    |
| `JobHandle`      | class | Per-job handle: events iterator, terminal `done` future, chunks. |
| `JobSubscription`| class | Result of `subscribe`; wraps a `JobHandle` plus replay metadata. |

## ARCPClient

```python
class ARCPClient:
    def __init__(
        self,
        *,
        client: ClientInfo,
        token: str,
        capabilities: Capabilities | None = None,
        features: tuple[str, ...] | None = None,
        auto_ack: AutoAckOptions | bool = False,
        handshake_timeout_sec: float = 5.0,
        logger: Any = None,
    ) -> None: ...

    async def connect(self, transport: Transport) -> SessionWelcomePayload: ...
    async def resume(self, transport: Transport, *, resume: SessionResume) -> SessionWelcomePayload: ...
    async def submit(
        self,
        *,
        agent: str,
        input: Any = None,
        lease_request: Lease | None = None,
        lease_constraints: LeaseConstraints | None = None,
        idempotency_key: str | None = None,
        max_runtime_sec: int | None = None,
        trace_id: str | None = None,
        parent_job_id: str | None = None,
    ) -> JobHandle: ...
    async def cancel_job(self, job_id: str, *, reason: str = "client.cancel") -> None: ...
    async def list_jobs(
        self,
        *,
        filter: ListJobsFilter | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> SessionJobsPayload: ...
    async def subscribe(
        self,
        job_id: str,
        *,
        history: bool = False,
        from_event_seq: int | None = None,
    ) -> JobSubscription: ...
    async def unsubscribe(self, job_id: str) -> None: ...
    async def ack(self, last_processed_seq: int) -> None: ...
    async def close(self, *, reason: str = "client.close") -> None: ...

    @property
    def session_id(self) -> str | None: ...
    @property
    def welcome(self) -> SessionWelcomePayload | None: ...
    @property
    def negotiated_features(self) -> tuple[str, ...]: ...
    @property
    def latest_event_seq(self) -> int: ...
    def has_feature(self, name: str) -> bool: ...
```

The constructor stages configuration; `connect` performs the
handshake and starts the read pump. `features=` defaults to
`V1_1_FEATURES` and is intersected against the runtime's set during
handshake. `auto_ack=True` enables a background task that sends
`session.ack` periodically when the `ack` feature is negotiated.

**Raises**: `InvalidRequestError` (feature-gated call without
negotiation), `UnauthenticatedError`, `PermissionDeniedError`,
`JobNotFoundError`, `DuplicateKeyError`, `AgentNotAvailableError`,
`AgentVersionNotAvailableError`, `ResumeWindowExpiredError`,
`TransportClosed`, `asyncio.TimeoutError` (handshake).

## AutoAckOptions

```python
class AutoAckOptions:
    every_sec: float = 0.5
```

Cadence for the background ack pump. Ignored when `ack` is not
negotiated.

## JobHandle

```python
class JobHandle:
    @property
    def agent_ref(self) -> str: ...
    @property
    def lease(self) -> Lease: ...
    @property
    def lease_constraints(self) -> LeaseConstraints | None: ...
    @property
    def budget(self) -> dict[str, str] | None: ...
    @property
    def trace_id(self) -> str | None: ...
    @property
    def done(self) -> Awaitable[JobResultPayload]: ...
    async def events(self) -> AsyncIterator[dict[str, Any]]: ...
    async def chunks(self) -> AsyncIterator[dict[str, Any]]: ...
    async def collect_chunks(self) -> bytes: ...
```

`events()` yields every event for the job in arrival order until
the terminal envelope. `chunks()` yields only `result_chunk` events.
`collect_chunks()` reassembles the chunk stream into `bytes`.

**Raises**: `ARCPError` subclasses on terminal `job.error`;
`TransportClosed` if the session ends mid-stream.

## JobSubscription

```python
class JobSubscription:
    job_id: str
    request_id: str
    subscribed_from: int
    replayed: bool
    handle: JobHandle
```

Returned by `ARCPClient.subscribe`; `handle` exposes the same
streaming surface as a locally-submitted job.

## See also

- Feature: [`../03-features/capability-negotiation.md`](../03-features/capability-negotiation.md).
- Feature: [`../03-features/event-ack.md`](../03-features/event-ack.md).
- Feature: [`../03-features/subscribe.md`](../03-features/subscribe.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §§6–8.
