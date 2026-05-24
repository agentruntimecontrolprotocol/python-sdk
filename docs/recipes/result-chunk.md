# Result chunk

An agent renders a 200 KB payload as a stream of `result_chunk`
events; the client collects them via `handle.collect_chunks()` and
asserts the reassembled bytes match the source.

Source: [`../../examples/result_chunk/`](../../examples/result_chunk/).

```sh
uv run python -m examples.result_chunk.server &
uv run python -m examples.result_chunk.client
```

## See also

- Guide: [Job events](../guides/job-events.md) — `job.result_chunk`.
- Guide: [Jobs](../guides/jobs.md) — Streaming results.
