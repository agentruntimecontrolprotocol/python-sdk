# Job events

> Spec reference: ARCP v1.1 §8

While a job runs, the runtime emits a stream of **typed events**. Every event has a `kind` discriminator, a `seq` (monotonically increasing sequence number), and a `job_id`.

## Event kinds

| Kind | Trigger | Key fields |
|---|---|---|
| `job.queued` | Job accepted by runtime | `job_id`, `agent`, `seq` |
| `job.started` | Agent function invoked | `job_id`, `resume_token`, `seq` |
| `job.log` | `ctx.log(level, msg)` | `level`, `message`, `seq` |
| `job.progress` | `ctx.progress(done, total)` | `done`, `total`, `seq` |
| `job.result_chunk` | `ctx.result_chunk(chunk)` | `chunk`, `seq` |
| `job.completed` | Agent returned | `result`, `seq` |
| `job.failed` | Agent raised an exception | `error`, `seq` |
| `job.cancelled` | Job cancelled | `seq` |
| `job.heartbeat` | Runtime keep-alive | `seq` |

## Subscribing to events

### Await completion only

```python
handle = await client.submit(agent="echo", input={"x": 1})
result = await handle.done
```

### Iterate all events

```python
handle = await client.submit(agent="echo", input={"x": 1})
async for event in handle.events():
    match event.kind:
        case "job.log":
            print(f"[{event.level}] {event.message}")
        case "job.progress":
            print(f"Progress: {event.done}/{event.total}")
        case "job.result_chunk":
            print(f"Chunk: {event.chunk}")
        case "job.completed":
            print(f"Result: {event.result}")
            break
        case "job.failed":
            raise RuntimeError(event.error)
```

### Subscribe without a job handle

Use `client.subscribe()` to attach to an existing job by ID:

```python
sub = await client.subscribe(job_id="job-abc123")
async for event in sub.events():
    ...
```

## Event acknowledgement

By default, events are auto-acknowledged. For explicit backpressure control:

```python
handle = await client.submit(
    agent="chunky",
    input={},
    auto_ack=False,
)
async for event in handle.events():
    process(event)
    await handle.ack(event.seq)  # acknowledge after processing
```

The runtime will not send the next event until the previous one is acknowledged.

## Typed event objects

Events are Pydantic models with a discriminated union on `kind`. You can use `isinstance` checks or `match` statements:

```python
from arcp import JobLogEvent, JobProgressEvent, JobCompletedEvent

async for event in handle.events():
    if isinstance(event, JobLogEvent):
        logger.info(event.message)
    elif isinstance(event, JobCompletedEvent):
        return event.result
```

## Related

- [Jobs guide](jobs.md)
- [Stream resume guide](resume.md)
- [Ack / backpressure recipe](../recipes/ack-backpressure.md)
- [Subscribe recipe](../recipes/subscribe.md)
