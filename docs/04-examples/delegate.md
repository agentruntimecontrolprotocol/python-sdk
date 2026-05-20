---
title: "Delegate"
sdk: python
order: 2
kind: example
---

A parent agent submits a child job to a peer runtime through
`JobContext.delegate(...)`, propagating `parent_job_id` and
`trace_id`, and requesting a strict-subset lease. Demonstrates how
delegation composes the recursive case of jobs / events / leases.

Source: [`../../examples/delegate/`](../../examples/delegate/).

```sh
uv run python -m examples.delegate.runtime &
uv run python -m examples.delegate.client
```

## See also

- Concepts: [`../02-concepts.md`](../02-concepts.md) — Delegation.
- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §10.
