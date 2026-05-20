---
title: "Subscribe"
sdk: python
spec_sections: ["§7.6"]
order: 5
kind: feature
---

## What it is

`job.subscribe` attaches a session to a job it did not submit, so an
operator client can stream events from a job owned by another
session. The runtime answers with `job.subscribed` (carrying the
subscription's high-water seq) and then forwards live `job.event` /
`job.result` / `job.error` envelopes onto the subscribing session's
write pump. With `history=True` or `from_event_seq=N`, the runtime
replays the matching prefix from the event log before live events
flow.

## Feature flag

`subscribe`

## Wire example

```json
{
  "arcp": "1.1",
  "id": "01J9SJ2...",
  "type": "job.subscribe",
  "session_id": "sess_01J9SHX...",
  "job_id": "job_01J9SHY...",
  "payload": {"history": true, "from_event_seq": null}
}
```

## Python API

```python
from arcp.client import ARCPClient

sub = await client.subscribe("job_01J9SHY...", history=True)
async for event in sub.handle.events():
    # elided: render event
    pass
result = await sub.handle.done
```

`ARCPClient.subscribe` at `arcp/_client/client.py:L376`; runtime fan-out
in `_handle_subscribe` at `arcp/_runtime/server.py:L684` and the
subscriber link plumbing in `arcp/_runtime/session.py:L24`.

## Failure modes

- `JOB_NOT_FOUND` — job id not in inventory
  (`arcp.errors.JobNotFoundError`).
- `PERMISSION_DENIED` — principal lacks read scope on the target job
  (`arcp.errors.PermissionDeniedError`).
- `INVALID_REQUEST` — `from_event_seq` outside the retained range.

## See also

- Example: [`../04-examples/subscribe.md`](../04-examples/subscribe.md).
- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §7.6.
