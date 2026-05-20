---
title: "Result chunks"
sdk: python
spec_sections: ["§8.4"]
order: 10
kind: feature
---

## What it is

Large terminal payloads stream as a sequence of `job.event` envelopes
with `payload.kind = "result_chunk"`, each carrying a `result_id`,
`seq`, and `bytes_b64` segment, terminated by `final: true` (and an
optional `summary`). The terminal `job.result` references the
`result_id` and contains no inline `result` body; mixing inline and
chunked is `INVALID_REQUEST`. Per-chunk size is capped per spec §14.

## Feature flag

`result_chunk`

## Wire example

```json
{
  "arcp": "1.1",
  "id": "01J9SJ7...",
  "type": "job.event",
  "session_id": "sess_01J9SHX...",
  "job_id": "job_01J9SHY...",
  "event_seq": 12,
  "payload": {
    "kind": "result_chunk",
    "result_id": "res_01J9SJ7...",
    "seq": 0,
    "bytes_b64": "SGVsbG8sIHdvcmxkIQ==",
    "final": false
  }
}
```

## Python API

Writer (runtime side):

```python
async def render(input_value, ctx):
    async with ctx.stream_result() as stream:
        for chunk in produce_chunks(input_value):
            await stream.write(chunk)
        await stream.close(summary="rendered 12 chunks")
```

Reader (client side):

```python
handle = await client.submit(agent="render", input={...})
data = await handle.collect_chunks()      # bytes
# or stream:
async for chunk in handle.chunks():
    pass
```

`JobContext.stream_result` at `arcp/_runtime/job.py:L259`;
`JobHandle.collect_chunks` at `arcp/_client/handles.py:L70`.

## Failure modes

- `INVALID_REQUEST` — inline `result` and `result_chunk` mixed in
  one job (`arcp.errors.InvalidRequestError`).
- `INTERNAL_ERROR` — chunk exceeds the per-spec size cap
  (`arcp.errors.InternalError`).

## See also

- Example: [`../04-examples/result-chunk.md`](../04-examples/result-chunk.md).
- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §8.4.
