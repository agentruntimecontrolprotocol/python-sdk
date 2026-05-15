---
title: "Quickstart"
sdk: python
order: 1
kind: guide
---

Run a client and a runtime in the same process over a paired in-memory
transport. No network, no auth backend, no external services.

```python
import asyncio

from arcp import (
    ARCPClient, ClientInfo, RuntimeInfo, pair_memory_transports,
)
from arcp.runtime import ARCPRuntime, StaticBearerVerifier

TOKEN = "demo"


async def echo(input_value, ctx):
    await ctx.log("info", "echo started")
    return {"echoed": input_value}


async def main() -> None:
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="quickstart", version="1.1.0"),
        bearer=StaticBearerVerifier({TOKEN: "me@example.com"}),
    )
    runtime.register_agent("echo", echo)

    client_t, server_t = pair_memory_transports()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(runtime.accept(server_t))

        client = ARCPClient(
            client=ClientInfo(name="quickstart-client", version="1.0.0"),
            token=TOKEN,
        )
        await client.connect(client_t)
        handle = await client.submit(agent="echo", input={"hi": 1})
        result = await handle.done
        print(result.result)
        await client.close()


asyncio.run(main())
```

Expected output:

```text
{'echoed': {'hi': 1}}
```

The runnable two-process WebSocket version lives in
[`../examples/submit_and_stream/`](../examples/submit_and_stream/).
For the wire-level walkthrough, continue to
[`02-concepts.md`](02-concepts.md).
