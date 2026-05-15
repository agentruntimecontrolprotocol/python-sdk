# result_chunk

Demonstrates §8.4 streamed results via `ctx.stream_result()` writer and
`handle.collect_chunks()` reader.

```
python examples/result_chunk/server.py     # terminal 1
python examples/result_chunk/client.py     # terminal 2
```

Advertised features: `["result_chunk"]`. Client success: reassembled
`len(blob) == result.result_size`; chunk count = 30.
