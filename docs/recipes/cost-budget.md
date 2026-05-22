# Cost budget

A client submits a job with `max_cost_usd: 0.05`; the agent
reports successive cost increments until the budget reaches zero,
and the next `ctx.report_cost(...)` call fails with `LeaseExceededError`.

Source: [`../../examples/cost_budget/`](../../examples/cost_budget/).

```sh
uv run python -m examples.cost_budget.runtime &
uv run python -m examples.cost_budget.client
```

## See also

- Guide: [Leases](../guides/leases.md) — cost budgets.
