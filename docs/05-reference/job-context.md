---
title: "arcp.runtime.JobContext"
sdk: python
order: 4
kind: reference
---

`JobContext` is the per-job API surface passed to every agent body.
It exposes job identity, the granted lease (and snapshot budget),
event emitters, and the lease-gated authorize seam.

## Symbols

| Name                              | Kind     | Summary                                               |
| --------------------------------- | -------- | ----------------------------------------------------- |
| `JobContext`                      | class    | Per-job runtime API.                                  |
| `ResultStream`                    | class    | Async-context-manager writer for chunked results.     |

## JobContext

```python
class JobContext:
    @property
    def job_id(self) -> str: ...
    @property
    def session_id(self) -> str: ...
    @property
    def agent(self) -> str: ...
    @property
    def agent_version(self) -> str | None: ...
    @property
    def agent_ref(self) -> str: ...
    @property
    def lease(self) -> Lease: ...
    @property
    def lease_constraints(self) -> LeaseConstraints | None: ...
    @property
    def budget(self) -> dict[str, Decimal]: ...
    @property
    def trace_id(self) -> str | None: ...

    async def log(self, level: str, message: str, **fields: Any) -> None: ...
    async def thought(self, text: str) -> None: ...
    async def status(self, phase: str, message: str | None = None) -> None: ...
    async def metric(self, body: dict[str, Any]) -> None: ...
    async def tool_call(self, body: dict[str, Any]) -> None: ...
    async def tool_result(self, body: dict[str, Any]) -> None: ...
    async def progress(
        self,
        *,
        current: int,
        total: int | None = None,
        units: str | None = None,
        message: str | None = None,
    ) -> None: ...
    async def result_chunk(self, body: dict[str, Any]) -> None: ...
    def stream_result(self, *, result_id: str | None = None) -> ResultStream: ...
    def authorize(self, op: str, target: str) -> LeaseOpContext: ...
```

Each emitter validates against the negotiated feature set —
`progress` and `result_chunk` raise `InvalidRequestError` when their
feature is absent. `authorize(op, target)` runs the lease subset test,
the `expires_at` deadline check, and the `cost.budget` floor check;
all three failure modes surface as typed exceptions.

**Raises**: `InvalidRequestError` (feature-gated emitter without
negotiation, negative metric, malformed body), `LeaseSubsetViolationError`,
`LeaseExpiredError`, `BudgetExhaustedError`.

## ResultStream

```python
class ResultStream:
    @property
    def result_id(self) -> str: ...
    async def write(self, chunk: bytes, *, final: bool = False) -> None: ...
    async def close(self, *, summary: str | None = None) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc) -> None: ...
```

Async-context-manager writer for `result_chunk` event streams.
Closing the stream emits the terminal `job.result` referencing
`result_id`.

**Raises**: `InvalidRequestError` if the agent body also emits an
inline `result`.

## See also

- Feature: [`../03-features/progress.md`](../03-features/progress.md).
- Feature: [`../03-features/result-chunk.md`](../03-features/result-chunk.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §§8–9.
