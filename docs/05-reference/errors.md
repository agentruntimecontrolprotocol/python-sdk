---
title: "arcp.errors"
sdk: python
order: 5
kind: reference
---

The 15 typed exceptions mirroring the spec §12 error codes plus the
`ERROR_CODES` tuple and the `error_class_for(code)` /
`error_from_payload(payload)` lookup helpers. Every error is a
subclass of `ARCPError`; subclasses fix `code` and `default_retryable`.
Re-exported from the top-level `arcp` package.

## Symbols

| Name                            | Code                          | Retryable |
| ------------------------------- | ----------------------------- | --------- |
| `ARCPError`                     | (base)                        | —         |
| `PermissionDeniedError`         | `PERMISSION_DENIED`           | no        |
| `LeaseSubsetViolationError`     | `LEASE_SUBSET_VIOLATION`      | no        |
| `JobNotFoundError`              | `JOB_NOT_FOUND`               | no        |
| `DuplicateKeyError`             | `DUPLICATE_KEY`               | no        |
| `AgentNotAvailableError`        | `AGENT_NOT_AVAILABLE`         | no        |
| `AgentVersionNotAvailableError` | `AGENT_VERSION_NOT_AVAILABLE` | no        |
| `CancelledError`                | `CANCELLED`                   | no        |
| `TimeoutError`                  | `TIMEOUT`                     | no        |
| `ResumeWindowExpiredError`      | `RESUME_WINDOW_EXPIRED`       | no        |
| `HeartbeatLostError`            | `HEARTBEAT_LOST`              | no        |
| `LeaseExpiredError`             | `LEASE_EXPIRED`               | no        |
| `BudgetExhaustedError`          | `BUDGET_EXHAUSTED`            | no        |
| `InvalidRequestError`           | `INVALID_REQUEST`             | no        |
| `UnauthenticatedError`          | `UNAUTHENTICATED`             | no        |
| `InternalError`                 | `INTERNAL_ERROR`              | yes       |
| `ERROR_CODES`                   | tuple of codes                | —         |
| `error_class_for(code)`         | function                      | —         |
| `error_from_payload(payload)`   | function                      | —         |

## ARCPError

```python
class ARCPError(Exception):
    code: ClassVar[str]
    default_retryable: ClassVar[bool]
    message: str
    retryable: bool
    details: dict[str, Any]

    def __init__(
        self,
        message: str,
        *,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None: ...
    def to_payload(self) -> dict[str, Any]: ...
```

`to_payload()` returns the wire-shape error body for inclusion in
`session.error` or `job.error`. Subclasses override `code` and
`default_retryable` only.

## error_class_for

```python
def error_class_for(code: str) -> type[ARCPError]: ...
```

Returns the typed class for a known wire `code`; unknown codes
collapse to `InternalError`.

## error_from_payload

```python
def error_from_payload(payload: dict[str, Any]) -> ARCPError: ...
```

Constructs the typed exception instance from a wire error body.
Used by `ARCPClient` to materialize `session.error` and `job.error`
payloads into raise-shaped values.

## See also

- Concepts: [`../02-concepts.md`](../02-concepts.md).
- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §12.
