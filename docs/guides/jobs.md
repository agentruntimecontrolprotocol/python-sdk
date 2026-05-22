# Jobs

> Spec reference: ARCP v1.1 §7

A **job** is a unit of work submitted by a client and executed by an agent function on the runtime.

## Submitting a job

```python
handle = await client.submit(
    agent="summarise",
    input={"url": "https://example.com"},
)
result = await handle.done
print(result.result)
```

### Submit options

| Parameter | Type | Description |
|---|---|---|
| `agent` | `str` | Agent name |
| `input` | `dict` | Arbitrary JSON-serialisable payload |
| `lease_request` | `dict` | Budget constraints (see [Leases](leases.md)) |
| `idempotency_key` | `str` | Deduplicate re-submissions (see below) |
| `agent_version` | `str` | Pin to a specific agent version |
| `resume_token` | `str` | Resume an interrupted stream |
| `resume_from_seq` | `int` | Replay from this event sequence number |

## Registering an agent

```python
async def summarise(input, ctx):
    url = input["url"]
    summary = await fetch_and_summarise(url)
    return {"summary": summary}

runtime.register_agent("summarise", summarise)
```

The agent function signature is always `async def fn(input: dict, ctx: JobContext) -> dict`.

## Job context

The `ctx` object gives agents access to logging, progress, streaming, cost reporting, and session identity.

```python
async def my_agent(input, ctx):
    await ctx.log("info", "starting")
    await ctx.progress(0, 100)

    for i in range(10):
        chunk = await do_work(i)
        await ctx.result_chunk(chunk)
        await ctx.progress((i + 1) * 10, 100)
        await ctx.report_cost(0.001)  # USD

    return {"done": True}
```

| Method | Description |
|---|---|
| `ctx.log(level, message)` | Emit a `job.log` event |
| `ctx.progress(done, total)` | Emit a `job.progress` event |
| `ctx.result_chunk(chunk)` | Emit a `job.result_chunk` event |
| `ctx.report_cost(usd)` | Accumulate cost against the lease |
| `ctx.principal` | The authenticated client identity |
| `ctx.job_id` | The current job ID |
| `ctx.session_id` | The current session ID |

## Streaming results

```python
handle = await client.submit(agent="stream", input={"n": 5})
async for event in handle.events():
    if event.kind == "job.result_chunk":
        print(event.chunk)  # each chunk as it arrives
    elif event.kind == "job.completed":
        print("Final:", event.result)
        break
```

## Cancellation

```python
handle = await client.submit(agent="slow", input={})
await asyncio.sleep(1.0)
await handle.cancel()
# handle.done raises JobCancelledError
```

Cancellation is cooperative: the runtime sends a cancellation signal and waits for the agent to finish its current operation. Agents can check `ctx.cancelled` to exit early.

## Idempotency

```python
import uuid

key = str(uuid.uuid4())  # generate once, store it

# First call — runs the job
handle1 = await client.submit(agent="charge", input={"amount": 100}, idempotency_key=key)
result1 = await handle1.done

# Second call with same key — returns the cached result immediately
handle2 = await client.submit(agent="charge", input={"amount": 100}, idempotency_key=key)
result2 = await handle2.done
assert result1.result == result2.result
```

## List jobs

```python
jobs = await client.list_jobs()
for job in jobs:
    print(job.job_id, job.state, job.agent)
```

## Related

- [Job events guide](job-events.md)
- [Leases guide](leases.md)
- [Stream resume guide](resume.md)
- [Recipes](../recipes.md)
