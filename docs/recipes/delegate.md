# Delegate

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

- Guide: [Delegation](../guides/delegation.md).
- Guide: [Architecture](../architecture.md) — Delegation (§10).
- Spec: [ARCP v1.1 §10](https://arcp.dev/spec/v1.1#section-10).
