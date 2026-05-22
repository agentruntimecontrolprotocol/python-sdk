# Leases

> Spec reference: ARCP v1.1 §9

A **lease** is a spending cap attached to a job. Clients request lease terms at submit time; the runtime enforces them. If a job exceeds its lease, the runtime cancels it and emits a `job.failed` event with `LeaseExceededError`.

## Cost budget

```python
handle = await client.submit(
    agent="gpt-4-summary",
    input={"text": long_text},
    lease_request={"max_cost_usd": 0.10},
)
```

The agent reports costs via `ctx.report_cost(usd)`:

```python
async def gpt_4_summary(input, ctx):
    response = await call_openai(input["text"])
    cost = response.usage.total_tokens * 0.00003
    await ctx.report_cost(cost)
    return {"summary": response.text}
```

When the accumulated cost exceeds `max_cost_usd`, the runtime raises `LeaseExceededError` and stops the job.

## Time budget

```python
handle = await client.submit(
    agent="slow-agent",
    input={},
    lease_request={"expires_in_s": 30},  # 30-second wall-clock limit
)
```

## Absolute expiry timestamp

```python
from datetime import datetime, timezone, timedelta

expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

handle = await client.submit(
    agent="slow-agent",
    input={},
    lease_request={"expires_at": expiry.isoformat()},
)
```

## Combining constraints

```python
handle = await client.submit(
    agent="research",
    input={"query": "quantum computing"},
    lease_request={
        "max_cost_usd": 0.50,
        "expires_in_s": 120,
    },
)
```

Both constraints are enforced independently. The job stops when either is exceeded.

## Handling lease errors

```python
from arcp import LeaseExceededError, LeaseExpiredError

try:
    result = await handle.done
except LeaseExceededError:
    print("Job exceeded cost budget")
except LeaseExpiredError:
    print("Job exceeded time budget")
```

## Runtime-side lease denial

Runtimes can reject lease requests they consider too large:

```python
runtime = ARCPRuntime(
    ...,
    max_lease_cost_usd=1.00,  # refuse any lease > $1.00
    max_lease_duration_s=300,  # refuse any lease > 5 minutes
)
```

If the requested lease exceeds these limits, submit raises `LeaseDeniedError`.

## Related

- [Jobs guide](jobs.md)
- [Cost budget recipe](../recipes/cost-budget.md)
- [Lease expires-at recipe](../recipes/lease-expires-at.md)
- [Lease violation recipe](../recipes/lease-violation.md)
- [Email vendor leases recipe](../recipes/email-vendor-leases.md)
