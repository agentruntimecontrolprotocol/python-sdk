# Getting started

This page walks you through a complete ARCP interaction in about five minutes: define an agent, start a runtime, connect a client, submit a job, and read the result.

## Prerequisites

```bash
pip install agentruntimecontrolprotocol
```

Requires Python 3.11+.

## Five-minute example

```python
import asyncio
from arcp import ARCPClient, ClientInfo, RuntimeInfo, pair_memory_transports
from arcp.runtime import ARCPRuntime, StaticBearerVerifier

TOKEN = "demo"


async def echo(input_value, ctx):
    """A trivial agent that echoes its input back."""
    await ctx.log("info", "echo started")
    return {"echoed": input_value}


async def main() -> None:
    # 1. Create a runtime and register an agent.
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="quickstart", version="1.1.0"),
        bearer=StaticBearerVerifier({TOKEN: "me@example.com"}),
    )
    runtime.register_agent("echo", echo)

    # 2. Create an in-process transport pair (no networking required).
    client_t, server_t = pair_memory_transports()

    async with asyncio.TaskGroup() as tg:
        # 3. Start the runtime — it will serve one connection then stop.
        tg.create_task(runtime.accept(server_t))

        # 4. Connect a client.
        client = ARCPClient(
            client=ClientInfo(name="quickstart-client", version="1.0.0"),
            token=TOKEN,
        )
        await client.connect(client_t)

        # 5. Submit a job and wait for completion.
        handle = await client.submit(agent="echo", input={"hi": 1})
        result = await handle.done
        print(result.result)   # {"echoed": {"hi": 1}}

        await client.close()


asyncio.run(main())
```

Save as `quickstart.py` and run:

```bash
uv run python quickstart.py
# or:
python quickstart.py
```

## What just happened

1. **Runtime** — `ARCPRuntime` is the server side. It authenticates clients, routes submitted jobs to registered agent functions, and streams events back.
2. **Agent** — a plain `async def` that receives `(input, ctx)`. Return value becomes the `JobResult`.
3. **Transport** — `pair_memory_transports()` returns two connected `Transport` objects. No sockets, no ports. See [Transports](transports.md) for WebSocket and stdio alternatives.
4. **Client** — `ARCPClient` manages the session, retries, and event subscription.
5. **Job handle** — `await handle.done` blocks until the runtime emits a `job.completed` event and returns the typed `JobResult`.

## Next steps

- [Architecture](architecture.md) — understand sessions, envelopes, and event kinds
- [Jobs guide](guides/jobs.md) — input validation, streaming results, cancellation
- [Leases guide](guides/leases.md) — cost and time budgets
- [Recipes](recipes.md) — copy-paste examples for common patterns
