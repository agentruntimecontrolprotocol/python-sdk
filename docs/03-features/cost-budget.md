---
title: "Cost budget"
sdk: python
spec_sections: ["§9.4", "§9.6"]
order: 8
kind: feature
---

## What it is

A lease may carry per-currency budget caps such as `["USD:5.00",
"tokens:10000"]`. The runtime decrements each counter when the
agent reports a `metric` event tagged with the matching currency,
and rejects further authorize calls once any counter hits zero with
`BUDGET_EXHAUSTED`. Delegated child jobs must request a strict
subset of the parent's per-currency caps (§9.4 subset rule).

## Feature flag

`cost.budget`

## Wire example

```json
{
  "arcp": "1.1",
  "id": "01J9SJ5...",
  "type": "job.submit",
  "session_id": "sess_01J9SHX...",
  "payload": {
    "agent": "summarize",
    "input": {"doc": "..."},
    "lease_request": {"cost.budget": ["USD:5.00", "tokens:10000"]}
  }
}
```

## Python API

```python
handle = await client.submit(
    agent="summarize",
    input={"doc": "..."},
    lease_request={"cost.budget": ["USD:5.00", "tokens:10000"]},
)

# Inside the agent body:
async def summarize(input_value, ctx):
    snapshot = ctx.budget          # dict[str, Decimal]
    await ctx.metric({"currency": "USD", "amount": "0.10"})
```

Initial snapshot: `initial_budget_from_lease` at
`arcp/_runtime/lease.py:L115`; per-event decrement and exhaustion
check in `Job.apply_cost_metric` at `arcp/_runtime/job.py:L68`;
`JobContext.budget` exposed at `arcp/_runtime/job.py:L174`.

## Failure modes

- `BUDGET_EXHAUSTED` — counter at zero on subsequent authorize or
  metric (`arcp.errors.BudgetExhaustedError`).
- `INVALID_REQUEST` — negative or unparsable amount, unknown
  currency syntax (`arcp.errors.InvalidRequestError`); also raised
  on a child delegation requesting a non-subset budget.

## See also

- Example: [`../04-examples/cost-budget.md`](../04-examples/cost-budget.md).
- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §9.6.
