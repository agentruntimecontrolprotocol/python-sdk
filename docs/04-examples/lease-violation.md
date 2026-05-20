---
title: "Lease violation"
sdk: python
order: 5
kind: example
---

An agent calls `ctx.authorize("net.fetch", "https://evil.example/")`
against a lease that does not grant that target; the runtime
emits `job.error` with code `LEASE_SUBSET_VIOLATION`. Demonstrates
the lease validator path and the failure surface in `arcp.errors`.

Source: [`../../examples/lease_violation/`](../../examples/lease_violation/).

```sh
uv run python -m examples.lease_violation.runtime &
uv run python -m examples.lease_violation.client
```

## See also

- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §9.1.
- Errors: [`../05-reference/errors.md`](../05-reference/errors.md).
