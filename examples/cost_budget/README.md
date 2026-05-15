# cost_budget

Demonstrates §9.6 — per-currency cost budgets with `BUDGET_EXHAUSTED`
surfaced via `tool_result.body.error`.

```
python examples/cost_budget/server.py     # terminal 1
python examples/cost_budget/client.py     # terminal 2
```

Advertised features: `["cost.budget"]`. Client success: one
`BUDGET_EXHAUSTED` observed in a `tool_result`; the
`cost.budget.remaining` snapshots are monotone non-increasing.
