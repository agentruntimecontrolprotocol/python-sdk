# Submit and stream

The hello-world example: a client submits one job and streams its
events until the terminal `job.result`. Demonstrates the connect /
submit / iterate / close lifecycle without leases, idempotency, or
v1.1 features.

Source: [`../../examples/submit_and_stream/`](../../examples/submit_and_stream/).

Run the two-process WebSocket variant:

```sh
uv run python -m examples.submit_and_stream.server &
uv run python -m examples.submit_and_stream.client
```

Or run the single-process paired-transport variant from
[Getting started](../getting-started.md).

## See also

- Guide: [Architecture](../architecture.md).
- Guide: [Jobs](../guides/jobs.md).
