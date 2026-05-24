# Stream resume

> Spec reference: ARCP v1.1 §6.3

If a connection drops while a job is running, the client can **resume** the event stream from where it left off — without resubmitting the job.

## How resume works

1. The runtime emits a `job.started` event containing a `resume_token`.
2. The client stores the token and the last acknowledged `event_seq`.
3. If the connection drops, the client reconnects and calls `client.resume(..., resume=SessionResume(...))`.
4. The runtime replays events from `event_seq + 1` onward.

The job itself is **not** re-executed. Only the event stream is replayed.

## Basic example

```python
import asyncio
from arcp import ARCPClient, ClientInfo, pair_memory_transports
from arcp.runtime import ARCPRuntime, RuntimeInfo, StaticBearerVerifier

async def slow_agent(input, ctx):
    for i in range(5):
        await ctx.progress(i, 5)
        await asyncio.sleep(0.1)
    return {"done": True}

runtime = ARCPRuntime(
    runtime=RuntimeInfo(name="resumable", version="1.0.0"),
    bearer=StaticBearerVerifier({"tok": "alice"}),
)
runtime.register_agent("slow", slow_agent)

async def main():
    client_t, server_t = pair_memory_transports()

    resume_token = None
    last_seq = 0

    async with asyncio.TaskGroup() as tg:
        tg.create_task(runtime.accept(server_t))

        client = ARCPClient(
            client=ClientInfo(name="client", version="1.0.0"),
            token="tok",
        )
        await client.connect(client_t)

        # First submission: capture resume_token from job.started
        handle = await client.submit(agent="slow", input={})

        async for event in handle.events():
            if event.kind == "job.started":
                resume_token = event.resume_token
            last_seq = event.seq

            if event.kind == "job.completed":
                print("Done:", event.result)
                break

        await client.close()

asyncio.run(main())
```

## Resuming after a disconnect

```python
# On a new connection, pass resume_token to re-attach to the running job
client2 = ARCPClient(client=ClientInfo(name="client2", version="1.0.0"), token="tok")
await client2.connect(new_transport)

handle = await client2.submit(
    agent="slow",
    input={},
    resume_token=resume_token,
    resume_from_seq=last_seq,
)
async for event in handle.events():
    print(event)  # replays from last_seq + 1
```

## Resume token lifetime

Resume tokens are valid until the job reaches a terminal state (`completed`, `failed`, or `cancelled`). After that, attempting to resume raises `ResumeError`.

## Related

- [Sessions guide](sessions.md)
- [Errors guide](errors.md) — `ResumeError`
- [Resume recipe](../recipes/resume.md)
