# Errors

> Spec reference: ARCP v1.1 §12

All ARCP exceptions inherit from `ARCPError`. The 15 typed exceptions map 1:1 to spec §12 error codes and are importable from `arcp`.

## Exception hierarchy

```
ARCPError
├── AuthenticationError      (auth.failed)
├── AuthorizationError       (auth.unauthorized)
├── AgentNotFoundError       (agent.not_found)
├── AgentVersionNotFoundError(agent.version_not_found)
├── JobNotFoundError         (job.not_found)
├── JobCancelledError        (job.cancelled)
├── LeaseExceededError       (lease.exceeded)
├── LeaseExpiredError        (lease.expired)
├── LeaseDeniedError         (lease.denied)
├── DelegationError          (delegation.invalid)
├── ResumeError              (resume.invalid)
├── CapabilityError          (capability.unsupported)
├── RateLimitError           (rate_limit.exceeded)
├── InternalError            (internal)
└── ProtocolError            (protocol)
```

## Handling errors

```python
from arcp import (
    ARCPError,
    AuthenticationError,
    LeaseExceededError,
    JobCancelledError,
    AgentNotFoundError,
)

try:
    handle = await client.submit(agent="my-agent", input={"x": 1})
    result = await handle.done
except AuthenticationError:
    # Token was rejected at session connect time
    print("Check your bearer token")
except AgentNotFoundError:
    # Agent name not registered on the runtime
    print("Agent not found")
except LeaseExceededError as e:
    # Job exceeded its cost or time budget
    print(f"Budget exceeded: {e.code}")
except JobCancelledError:
    # Job was cancelled (by client or runtime)
    print("Job was cancelled")
except ARCPError as e:
    # Catch-all for any other ARCP error
    print(f"ARCP error: {e.code} — {e.message}")
```

## Error attributes

Every `ARCPError` has:

| Attribute | Type | Description |
|---|---|---|
| `code` | `str` | Spec error code, e.g. `"lease.exceeded"` |
| `message` | `str` | Human-readable description |
| `data` | `dict \| None` | Optional structured detail |

## Raising errors from agents

Agents can signal well-typed failures by raising `ARCPError` subclasses:

```python
from arcp import AuthorizationError

async def admin_only(input, ctx):
    if ctx.principal != "admin@example.com":
        raise AuthorizationError("only admin can call this agent")
    return {"secret": 42}
```

The runtime converts the exception into a `job.failed` event with the matching error code.

## Catching errors inside agents

Unhandled exceptions from agent functions are caught by the runtime and emitted as `job.failed` with `InternalError`. Catch expected exceptions explicitly:

```python
async def fragile_agent(input, ctx):
    try:
        result = await call_external_api(input)
    except httpx.TimeoutException as e:
        raise InternalError(f"external API timed out: {e}") from e
    return result
```

## Related

- [Troubleshooting](../troubleshooting.md)
- [Leases guide](leases.md) — `LeaseExceededError`, `LeaseExpiredError`
- [Auth guide](auth.md) — `AuthenticationError`, `AuthorizationError`
