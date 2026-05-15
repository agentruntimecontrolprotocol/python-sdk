---
title: "Progress"
sdk: python
spec_sections: ["§8.2"]
order: 9
kind: feature
---

## What it is

`job.event` with `payload.kind = "progress"` reports a numeric
position against an optional total, with optional `units` and
`message`. Negative `current` is rejected at the runtime boundary
with `INVALID_REQUEST`; `total` is optional (open-ended progress
streams).

## Feature flag

`progress`

## Wire example

```json
{
  "arcp": "1",
  "id": "01J9SJ6...",
  "type": "job.event",
  "session_id": "sess_01J9SHX...",
  "job_id": "job_01J9SHY...",
  "event_seq": 7,
  "payload": {
    "kind": "progress",
    "current": 42,
    "total": 100,
    "units": "files",
    "message": "scanned 42 of 100"
  }
}
```

## Python API

```python
async def scan(input_value, ctx):
    files = list_files(input_value["root"])
    for i, path in enumerate(files, 1):
        # elided: process path
        await ctx.progress(current=i, total=len(files), units="files")
```

Implementation: `JobContext.progress` at `arcp/_runtime/job.py:L227`.

## Failure modes

- `INVALID_REQUEST` — negative `current`, negative `total`, or
  non-numeric values (`arcp.errors.InvalidRequestError`).

## See also

- Example: [`../04-examples/progress.md`](../04-examples/progress.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §8.2.
