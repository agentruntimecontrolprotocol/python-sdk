---
title: "Idempotent retry"
sdk: python
order: 4
kind: example
---

The client submits the same `(principal, agent, input,
idempotency_key)` twice and receives the same `job_id` both times.
Demonstrates the spec §7.4 deduplication contract on the in-memory
idempotency store.

Source: [`../../examples/idempotent_retry/`](../../examples/idempotent_retry/).

```sh
uv run python -m examples.idempotent_retry.runtime &
uv run python -m examples.idempotent_retry.client
```

## See also

- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §7.4.
