---
title: "Lease expires_at"
sdk: python
spec_sections: ["§9.5"]
order: 7
kind: feature
---

## What it is

A client may attach an absolute UTC deadline to its lease request;
the runtime echoes the granted deadline in
`job.accepted.payload.lease_constraints.expires_at` and starts a
watchdog. Any `JobContext.authorize(op, target)` call after the
deadline rejects with `LEASE_EXPIRED`; the in-flight job terminates
with `job.error` carrying the same code.

## Feature flag

`lease_expires_at`

## Wire example

```json
{
  "arcp": "1",
  "id": "01J9SJ4...",
  "type": "job.submit",
  "session_id": "sess_01J9SHX...",
  "payload": {
    "agent": "scrape",
    "input": {"url": "https://example.com"},
    "lease_request": {"net.fetch": ["https://example.com/**"]},
    "lease_constraints": {"expires_at": "2026-05-14T18:30:00Z"}
  }
}
```

## Python API

```python
from arcp import LeaseConstraints

handle = await client.submit(
    agent="scrape",
    input={"url": "https://example.com"},
    lease_request={"net.fetch": ["https://example.com/**"]},
    lease_constraints=LeaseConstraints(expires_at="2026-05-14T18:30:00Z"),
)
```

Validator: `validate_lease_constraints` at
`arcp/_runtime/lease.py:L51`; watchdog in `_lease_watchdog` at
`arcp/_runtime/server.py:L646`.

## Failure modes

- `INVALID_REQUEST` — past timestamp or non-UTC value
  (`arcp.errors.InvalidRequestError`).
- `LEASE_EXPIRED` — emitted on first authorize after the deadline,
  and as the terminal `job.error` code
  (`arcp.errors.LeaseExpiredError`).

## See also

- Example: [`../04-examples/lease-expires-at.md`](../04-examples/lease-expires-at.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §9.5.
