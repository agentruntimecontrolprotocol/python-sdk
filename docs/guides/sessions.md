# Sessions

> Spec reference: ARCP v1.1 §6

A **session** is the top-level connection between an `ARCPClient` and an `ARCPRuntime`. Sessions carry authentication, capability negotiation, and the full job lifecycle.

## Session lifecycle

```
Client                          Runtime
  │                               │
  ├── connect (transport) ──────► │
  │                               ├── verify bearer token
  │                               ├── negotiate capabilities
  ├── submit job ─────────────► │
  │ ◄── event stream ────────── │
  ├── close ─────────────────► │
  │                               │
```

## Creating a session

```python
import asyncio
from arcp import ARCPClient, ClientInfo, pair_memory_transports
from arcp.runtime import ARCPRuntime, RuntimeInfo, StaticBearerVerifier

runtime = ARCPRuntime(
    runtime=RuntimeInfo(name="my-service", version="1.0.0"),
    bearer=StaticBearerVerifier({"secret": "alice@example.com"}),
)
runtime.register_agent("ping", lambda input, ctx: {"pong": True})

client_t, server_t = pair_memory_transports()

async with asyncio.TaskGroup() as tg:
    tg.create_task(runtime.accept(server_t))

    client = ARCPClient(
        client=ClientInfo(name="my-client", version="1.0.0"),
        token="secret",
    )
    await client.connect(client_t)

    handle = await client.submit(agent="ping", input={})
    result = await handle.done
    print(result.result)  # {"pong": True}

    await client.close()
```

## Session identity

Every session has a `session_id` (a UUID assigned by the runtime at connect time). Job IDs are scoped to the session.

```python
print(client.session_id)  # e.g. "3f8a1b2c-..."
```

## Session expiry

Sessions do not expire on their own — they end when the transport closes. Use a heartbeat or WebSocket ping to keep long-lived sessions alive across network boundaries.

## Multiple sessions

Each call to `client.connect()` creates a new session. Jobs from one session are not visible to another.

```python
# Two independent sessions to the same runtime
for _ in range(2):
    c_t, s_t = pair_memory_transports()
    tg.create_task(runtime.accept(s_t))
    c = ARCPClient(client=ClientInfo(name="c", version="1.0.0"), token="secret")
    await c.connect(c_t)
    ...
```

## Related

- [Authentication guide](auth.md) — bearer tokens and custom verifiers
- [Stream resume guide](resume.md) — reconnecting interrupted sessions
- [Transports](../transports.md) — transport options
