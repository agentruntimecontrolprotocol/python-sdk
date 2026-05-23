# Multi-Agent Budget

This recipe shows how to coordinate cost budgets across a chain of agents:
a **coordinator** agent receives a top-level budget, allocates a fraction to
each **worker** sub-job, and enforces that the sum never exceeds the original
cap.

## Architecture

```
Caller ──submit(budget=$1.00)──► Coordinator
                                      │
                     ┌────────────────┼────────────────┐
                     ▼                ▼                ▼
               Worker A          Worker B          Worker C
             (budget=$0.33)    (budget=$0.33)    (budget=$0.33)
```

## Prerequisites

```bash
uv add agentruntimecontrolprotocol
```

## Implementation

```python
import asyncio
from decimal import Decimal

from arcp import ARCPClient, ARCPRuntime, JobContext
from arcp.auth import StaticBearerVerifier
from arcp.models import CostBudget, Lease
from arcp.transport import pair_memory_transports

# ---------------------------------------------------------------------------
# Worker agent — does the actual work within its allocated budget
# ---------------------------------------------------------------------------

async def worker_agent(ctx: JobContext) -> None:
    async for item in ctx.input_stream():
        # Simulate work that costs money (e.g., an LLM call).
        cost = Decimal("0.01")
        await ctx.record_cost(usd=cost)
        await ctx.emit_event("result.chunk", {"output": f"processed: {item}"})


# ---------------------------------------------------------------------------
# Coordinator agent — splits budget and fans out to workers
# ---------------------------------------------------------------------------

async def coordinator_agent(ctx: JobContext) -> None:
    # Read the top-level budget granted by the caller.
    top_budget: Decimal = ctx.lease.cost_budget.usd  # type: ignore[union-attr]

    # Collect all input items first so we know how many workers we need.
    items = [item async for item in ctx.input_stream()]
    n_workers = max(1, len(items))
    per_worker = (top_budget / n_workers).quantize(Decimal("0.0001"))

    await ctx.emit_event(
        "coordinator.plan",
        {
            "top_budget_usd": str(top_budget),
            "workers": n_workers,
            "per_worker_usd": str(per_worker),
        },
    )

    # Submit one sub-job per item, each with its slice of the budget.
    # Re-use the same runtime's client — coordinator is itself a client.
    async with ARCPClient(client_transport, token="secret") as sub_client:
        handles = [
            await sub_client.submit(
                agent="worker",
                input=[item],
                lease=Lease(cost_budget=CostBudget(usd=per_worker)),
            )
            for item in items
        ]

        # Stream all worker results back to the coordinator's output.
        async def relay(handle, worker_id: int) -> None:
            async for event in handle.events():
                if event.kind == "result.chunk":
                    await ctx.emit_event(
                        "result.chunk",
                        {"worker": worker_id, **event.data},
                    )
            await handle.done

        await asyncio.gather(*[relay(h, i) for i, h in enumerate(handles)])


# ---------------------------------------------------------------------------
# Runtime setup
# ---------------------------------------------------------------------------

server_transport, client_transport = pair_memory_transports()

runtime = ARCPRuntime(
    transport=server_transport,
    auth=StaticBearerVerifier("secret"),
)
runtime.register_agent("coordinator", coordinator_agent)
runtime.register_agent("worker", worker_agent)
```

## Caller

```python
async def main() -> None:
    async with ARCPClient(client_transport, token="secret") as client:
        handle = await client.submit(
            agent="coordinator",
            input=[
                {"task": "summarise document A"},
                {"task": "summarise document B"},
                {"task": "summarise document C"},
            ],
            lease=Lease(cost_budget=CostBudget(usd=Decimal("1.00"))),
        )

        async for event in handle.events():
            print(event.kind, event.data)

        await handle.done


asyncio.run(main())
```

## Budget enforcement

| Layer | Mechanism |
|---|---|
| Top-level cap | Caller's `Lease.cost_budget` — runtime refuses new jobs that would exceed it |
| Per-worker cap | Coordinator passes a fraction to each sub-job's `Lease.cost_budget` |
| Cost recording | `ctx.record_cost()` debits the worker's budget in real-time |
| Violation | `LeaseCostExceeded` is raised in the worker; propagates to coordinator |

If a worker exceeds its slice the coordinator catches a `LeaseCostExceeded`
exception from `handle.done` and can decide whether to cancel remaining workers
or continue with a warning.

## Handling budget overruns

```python
from arcp.errors import LeaseCostExceeded

async def relay_safe(handle, worker_id: int) -> None:
    try:
        async for event in handle.events():
            if event.kind == "result.chunk":
                await ctx.emit_event("result.chunk", {"worker": worker_id, **event.data})
        await handle.done
    except LeaseCostExceeded:
        await ctx.emit_event(
            "coordinator.worker_overran",
            {"worker": worker_id},
        )
```

## Related

- [Leases guide](../guides/leases.md)
- [Cost budget recipe](cost-budget.md)
- [Lease violation recipe](lease-violation.md)
- [Delegation guide](../guides/delegation.md)
