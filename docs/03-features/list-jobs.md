---
title: "List jobs"
sdk: python
spec_sections: ["§6.6"]
order: 4
kind: feature
---

## What it is

`session.list_jobs` is a synchronous request/response that returns the
visible job inventory for the calling principal, optionally filtered
by status and agent and paged by opaque cursor. The runtime echoes
the originating envelope `id` in `session.jobs.payload.request_id`.
v1.0 fallback: clients track their own `submit`/event history.

## Feature flag

`list_jobs`

## Wire example

```json
{
  "arcp": "1.1",
  "id": "01J9SJ1...",
  "type": "session.list_jobs",
  "session_id": "sess_01J9SHX...",
  "payload": {
    "filter": {"status": ["running"], "agent": "weekly-report"},
    "limit": 50,
    "cursor": null
  }
}
```

## Python API

```python
from arcp import ListJobsFilter
from arcp.client import ARCPClient

reply = await client.list_jobs(
    filter=ListJobsFilter(status=["running"], agent="weekly-report"),
    limit=50,
    cursor=None,
)
for row in reply.jobs:
    print(row.job_id, row.status)
next_cursor = reply.next_cursor
```

Implementation: `ARCPClient.list_jobs` at `arcp/_client/client.py:L354`;
runtime handler at `arcp/_runtime/server.py:L426`.

## Failure modes

- `INVALID_REQUEST` — malformed filter or out-of-range limit
  (`arcp.errors.InvalidRequestError`).
- Default scope is the calling principal; cross-principal listing
  requires runtime authorization policy.

## See also

- Example: [`../04-examples/list-jobs.md`](../04-examples/list-jobs.md).
- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §6.6.
