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
| `lease_constraints` | `dict` | Optional absolute expiry and related constraints |
| `max_runtime_sec` | `int` | Maximum runtime before timeout |
| `trace_id` | `str` | Optional trace correlation id |
| `parent_job_id` | `str` | Parent job for delegation or tracing |

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
    await ctx.progress(0, total=100)

    for i in range(10):
        chunk = await do_work(i)
        await ctx.result_chunk(chunk)
        await ctx.progress((i + 1) * 10, total=100)
        await ctx.metric({"name": "cost.inference", "value": 0.001, "unit": "USD"})

    return {"done": True}
```

| Method | Description |
|---|---|
| `ctx.log(level, message)` | Emit a `job.log` event |
| `ctx.progress(current, total=..., units=..., message=...)` | Emit a `job.progress` event |
| `ctx.result_chunk(chunk)` | Emit a `job.result_chunk` event |
| `ctx.metric(body)` | Emit a `metric` event |
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
await client.cancel_job(handle.job_id)
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
