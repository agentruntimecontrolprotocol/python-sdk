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

    async with ctx.stream_result() as stream:
        for i in range(10):
            await stream.write(await do_work(i))
            await ctx.progress((i + 1) * 10, total=100)
            await ctx.metric({"name": "cost.inference", "value": 0.001, "unit": "USD"})

    return {"done": True}
```

| Member | Description |
|---|---|
| `ctx.log(level, message, attributes=...)` | Emit a `log` event (`level` ∈ `debug`/`info`/`warn`/`error`) |
| `ctx.progress(current, *, total=..., units=..., message=...)` | Emit a `progress` event (`total` is keyword-only) |
| `ctx.result_chunk(body)` | Emit one `result_chunk` event |
| `ctx.stream_result()` | Open a `ResultStream` writer for chunked results |
| `ctx.metric(body)` | Emit a `metric` event (cost.* automatically decrements budget) |
| `ctx.status(phase, message=...)` | Emit a `status` event |
| `ctx.tool_call(body)` / `ctx.tool_result(body)` | Emit MCP-style tool-call events |
| `ctx.authorize(capability, target)` | Validate a lease op for `capability:target` |
| `ctx.rotate_credential(id, new_value)` | Publish a credential rotation |
| `ctx.budget` | Read-only snapshot of remaining `cost.budget` |
| `ctx.lease` / `ctx.lease_constraints` | The lease attached to this job |
| `ctx.job_id` / `ctx.session_id` / `ctx.trace_id` | Identity helpers |
| `ctx.agent` / `ctx.agent_version` / `ctx.agent_ref` | Agent name + selected version |

## Streaming results

The agent returns chunks through a `ResultStream`; the client consumes them via `JobHandle.chunks()` and joins on `JobHandle.done` for the terminal `job.result`.

```python
handle = await client.submit(agent="stream", input={"n": 5})

# Collect chunks as they arrive (each chunk is a dict from the wire body).
async for chunk in handle.chunks():
    print("chunk:", chunk)

# All other event kinds (log, progress, metric, status, …) are surfaced on
# `events()` and the terminal payload is awaited via `done`.
result = await handle.done
print("final:", result.result_size, "bytes")
```

## Cancellation

```python
handle = await client.submit(agent="slow", input={})
await asyncio.sleep(1.0)
await client.cancel_job(handle.job_id)
# handle.done resolves to a JobResultPayload with final_status="cancelled".
result = await handle.done
assert result.final_status == "cancelled"
```

Cancellation is cooperative: the runtime cancels the running task, which surfaces in the agent coroutine as `asyncio.CancelledError`. Agents should let it propagate (or catch, clean up, and re-raise).

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
