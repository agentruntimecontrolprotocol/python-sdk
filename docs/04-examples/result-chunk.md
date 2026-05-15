---
title: "Result chunk"
sdk: python
order: 18
kind: example
---

An agent renders a 200 KB payload as a stream of `result_chunk`
events; the client collects them via `handle.collect_chunks()` and
asserts the reassembled bytes match the source.

Source: [`../../examples/result_chunk/`](../../examples/result_chunk/).

```sh
uv run python -m examples.result_chunk.runtime &
uv run python -m examples.result_chunk.client
```

## See also

- Feature: [`../03-features/result-chunk.md`](../03-features/result-chunk.md).
