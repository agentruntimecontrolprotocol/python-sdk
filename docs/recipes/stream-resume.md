# Stream Resume

This recipe shows a production-ready reconnection loop that transparently
resumes a long-running ARCP job after a network interruption, without
reprocessing already-delivered events.

See the [resume guide](../guides/resume.md) for the underlying concepts
(spec [§6.3](https://arcp.dev/spec/v1.1#section-6.3)).

## The problem

Long-running jobs (batch processing, LLM pipelines, multi-step workflows) are
vulnerable to transient network failures.  Without resume support you must
either re-run the entire job or add bespoke checkpointing logic.  ARCP's
`resume_token` + `resume_from_seq` mechanism solves this at the protocol layer.

## Complete reconnection loop

```python
import asyncio
import logging
from typing import AsyncIterator

from arcp import ARCPClient, ARCPRuntime, JobContext
from arcp.auth import StaticBearerVerifier
from arcp.errors import JobNotFound, SessionExpired
from arcp.models import JobHandle
from arcp.transport import pair_memory_transports

log = logging.getLogger(__name__)

MAX_RETRIES = 10
BACKOFF_BASE = 0.5  # seconds
BACKOFF_CAP = 30.0  # seconds


async def events_with_resume(
    client: ARCPClient,
    handle: JobHandle,
    *,
    max_retries: int = MAX_RETRIES,
) -> AsyncIterator[object]:
    """
    Yield events from *handle*, resuming transparently on disconnection.

    Raises the underlying exception after *max_retries* consecutive failures.
    """
    last_seq: int | None = None
    attempt = 0

    while True:
        try:
            async for event in handle.events(resume_from_seq=last_seq):
                last_seq = event.seq
                attempt = 0  # reset backoff on successful delivery
                yield event

            # Clean exit — job finished.
            return

        except (ConnectionError, TimeoutError, OSError) as exc:
            attempt += 1
            if attempt > max_retries:
                raise

            delay = min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_CAP)
            log.warning(
                "Stream disconnected (attempt %d/%d), resuming in %.1fs: %s",
                attempt,
                max_retries,
                delay,
                exc,
            )
            await asyncio.sleep(delay)

            # Re-attach to the same job using the resume token.
            handle = await client.attach(
                job_id=handle.job_id,
                resume_token=handle.resume_token,
            )

        except SessionExpired:
            # The session (and its resume tokens) has expired — nothing we can do.
            log.error("Session expired; cannot resume job %s", handle.job_id)
            raise

        except JobNotFound:
            log.error("Job %s not found; it may have been purged", handle.job_id)
            raise


# ---------------------------------------------------------------------------
# Example agent
# ---------------------------------------------------------------------------

async def slow_agent(ctx: JobContext) -> None:
    """Emits 20 events with 0.5 s gaps — easy to interrupt for testing."""
    for i in range(20):
        await asyncio.sleep(0.5)
        await ctx.emit_event("progress", {"step": i + 1, "total": 20})


# ---------------------------------------------------------------------------
# Runtime setup
# ---------------------------------------------------------------------------

server_transport, client_transport = pair_memory_transports()

runtime = ARCPRuntime(
    transport=server_transport,
    auth=StaticBearerVerifier("secret"),
)
runtime.register_agent("slow", slow_agent)


# ---------------------------------------------------------------------------
# Caller — uses the resilient helper
# ---------------------------------------------------------------------------

async def main() -> None:
    async with ARCPClient(client_transport, token="secret") as client:
        handle = await client.submit(agent="slow", input=[])

        async for event in events_with_resume(client, handle):
            pct = 100 * event.data["step"] // event.data["total"]
            print(f"[{pct:3d}%] step {event.data['step']}")

        await handle.done
        print("Job completed successfully")


asyncio.run(main())
```

## Sequence diagram

```
Client          Network         Runtime
  │──submit()──────────────────►│
  │◄──handle(job_id, token)──────│
  │──events()───────────────────►│
  │◄──event(seq=0)───────────────│
  │◄──event(seq=1)───────────────│
  │        ✗  disconnect  ✗      │  (job continues running)
  │                              │
  │── (backoff delay) ──────────►│
  │──attach(job_id, token)───────►│
  │──events(resume_from_seq=1)──►│
  │◄──event(seq=2)───────────────│  ← no gap, no duplicate
  │◄──event(seq=3)───────────────│
  │◄──job.done───────────────────│
```

## Key properties

| Property | Detail |
|---|---|
| **No duplicates** | `resume_from_seq` instructs the runtime to skip already-delivered events |
| **No missed events** | The runtime buffers events until the session expires |
| **Idempotent attach** | `client.attach()` does not create a new job; it re-joins the existing one |
| **Backoff** | Exponential with cap prevents thundering-herd on reconnect |
| **Session expiry** | `SessionExpired` is non-retryable — surface it to the user |

## Token lifetime

Resume tokens expire with the session (default 24 h, configurable on the
runtime).  Jobs that run longer than the session TTL cannot be resumed after
expiry; design long-running pipelines to checkpoint intermediate results as
ARCP events.

## Testing the reconnection loop

```python
import unittest.mock

# Inject a transient failure after the first event.
original_events = handle.events
call_count = 0

async def flaky_events(**kw):
    global call_count
    call_count += 1
    async for event in original_events(**kw):
        yield event
        if call_count == 1:  # fail after first event on first call
            raise ConnectionError("simulated drop")

handle.events = flaky_events
```

## Related

- [Resume guide](../guides/resume.md)
- [Sessions guide](../guides/sessions.md)
- [Resume recipe](resume.md) — minimal single-reconnect example
- [Errors guide](../guides/errors.md)
