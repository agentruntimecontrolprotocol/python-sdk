# Troubleshooting

Common errors, what they mean, and how to fix them.

## Error reference

All SDK exceptions inherit from `ARCPError` and map to a spec §12 error code.

| Exception | Code | Meaning |
|---|---|---|
| `AuthenticationError` | `auth.failed` | Bearer token rejected |
| `AuthorizationError` | `auth.unauthorized` | Token valid but principal lacks permission |
| `AgentNotFoundError` | `agent.not_found` | No agent registered under that name |
| `AgentVersionNotFoundError` | `agent.version_not_found` | Agent exists but requested version does not |
| `JobNotFoundError` | `job.not_found` | Job ID does not exist in this session |
| `JobCancelledError` | `job.cancelled` | Job was cancelled before completion |
| `LeaseExceededError` | `lease.exceeded` | Job exceeded its cost or time budget |
| `LeaseExpiredError` | `lease.expired` | Job's `expires_at` timestamp passed |
| `LeaseDeniedError` | `lease.denied` | Runtime refused the requested lease terms |
| `DelegationError` | `delegation.invalid` | Delegation token is malformed or untrusted |
| `ResumeError` | `resume.invalid` | Resume token is unknown or expired |
| `CapabilityError` | `capability.unsupported` | Client requested a feature the runtime doesn't support |
| `RateLimitError` | `rate_limit.exceeded` | Too many requests |
| `InternalError` | `internal` | Unexpected runtime error |
| `ProtocolError` | `protocol` | Malformed envelope received |

## Common issues

### `AuthenticationError: auth.failed`

**Cause:** The bearer token passed to `ARCPClient` was not recognised by the runtime's verifier.

**Fix:** Check that the token appears in `StaticBearerVerifier` or that your custom verifier returns a non-`None` principal.

```python
# Wrong — token not in the map
bearer = StaticBearerVerifier({"valid-token": "alice@example.com"})
client = ARCPClient(..., token="wrong-token")

# Right
client = ARCPClient(..., token="valid-token")
```

### `AgentNotFoundError: agent.not_found`

**Cause:** The agent name passed to `client.submit()` was not registered on the runtime.

**Fix:** Check spelling and confirm `runtime.register_agent(name, fn)` was called before `runtime.accept()`.

### `LeaseExceededError: lease.exceeded`

**Cause:** The job emitted a cost metric via `ctx.metric(...)` and the running total exceeded `lease_request["max_cost_usd"]`.

**Fix:** Either raise the budget in `lease_request` or reduce cost reporting in the agent.

### Event stream ends with no `job.completed`

**Cause:** The connection dropped and stream resume was not configured.

**Fix:** Pass the current `resume_token` from the session handshake to a new `submit()` call. See [Stream resume guide](guides/resume.md).

### `RuntimeError: TaskGroup already finished`

**Cause:** `runtime.accept()` was awaited outside an `asyncio.TaskGroup`, and the client connected after `accept()` returned.

**Fix:** Always run `runtime.accept()` and `client.connect()` concurrently:

```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(runtime.accept(server_t))
    await client.connect(client_t)
    ...
```

## Debugging tips

### Enable debug logging

```python
import logging
logging.getLogger("arcp").setLevel(logging.DEBUG)
```

This prints every envelope sent and received, which is usually enough to diagnose protocol issues.

### Inspect raw events

Subscribe to the raw event stream before awaiting `handle.done`:

```python
handle = await client.submit(agent="echo", input={"x": 1})
async for event in handle.events():
    print(event)  # each JobEvent as it arrives
```

### Record and replay

```bash
arcp tail ws://localhost:8080/arcp JOB_ID --token TOKEN --output events.jsonl
arcp replay events.jsonl
```
