# Idempotent retry

The client submits the same `(principal, agent, input,
idempotency_key)` twice and receives the same `job_id` both times.
Demonstrates the spec §7.4 deduplication contract on the in-memory
idempotency store.

Source: [`../../examples/idempotent_retry/`](../../examples/idempotent_retry/).

```sh
uv run python -m examples.idempotent_retry.server &
uv run python -m examples.idempotent_retry.client
```

## See also

- Guide: [Jobs](../guides/jobs.md) — Idempotency.
- Spec: [ARCP v1.1 §7.4](https://arcp.dev/spec/v1.1#section-7.4).
