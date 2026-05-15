---
title: "Cost budget"
sdk: python
order: 16
kind: example
---

A client submits a job with `cost.budget: ["USD:0.05"]`; the agent
reports successive `metric` events until the budget reaches zero,
and the next authorize call fails with `BUDGET_EXHAUSTED`.

Source: [`../../examples/cost_budget/`](../../examples/cost_budget/).

```sh
uv run python -m examples.cost_budget.runtime &
uv run python -m examples.cost_budget.client
```

## See also

- Feature: [`../03-features/cost-budget.md`](../03-features/cost-budget.md).
