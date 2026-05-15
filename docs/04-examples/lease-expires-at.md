---
title: "Lease expires_at"
sdk: python
order: 15
kind: example
---

A client submits a job with a 2-second `expires_at`; the agent
sleeps past the deadline and the next `ctx.authorize(...)` raises
`LEASE_EXPIRED`, terminating the job with the same code.

Source: [`../../examples/lease_expires_at/`](../../examples/lease_expires_at/).

```sh
uv run python -m examples.lease_expires_at.runtime &
uv run python -m examples.lease_expires_at.client
```

## See also

- Feature: [`../03-features/lease-expires-at.md`](../03-features/lease-expires-at.md).
