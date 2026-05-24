# Lease violation

An agent calls `ctx.authorize("net.fetch", "https://evil.example/")`
against a lease that does not grant that target; the runtime
emits `job.error` with code `LEASE_SUBSET_VIOLATION`. Demonstrates
the lease validator path and the failure surface in `arcp._errors`.

Source: [`../../examples/lease_violation/`](../../examples/lease_violation/).

```sh
uv run python -m examples.lease_violation.server &
uv run python -m examples.lease_violation.client
```

## See also

- Guide: [Leases](../guides/leases.md).
- Guide: [Errors](../guides/errors.md).
- Spec: [ARCP v1.1 §9.1](https://arcp.dev/spec/v1.1#section-9.1).
