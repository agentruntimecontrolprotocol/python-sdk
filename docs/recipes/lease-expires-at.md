# Lease expires_at

A client submits a job with a 2-second `expires_at`; the agent
sleeps past the deadline and the next `ctx.authorize(...)` raises
`LeaseExpiredError`, terminating the job with the same code.

Source: [`../../examples/lease_expires_at/`](../../examples/lease_expires_at/).

```sh
uv run python -m examples.lease_expires_at.runtime &
uv run python -m examples.lease_expires_at.client
```

## See also

- Guide: [Leases](../guides/leases.md) — absolute expiry timestamp.
