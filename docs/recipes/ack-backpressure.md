# Ack back-pressure

The runtime emits events faster than the client acknowledges them;
once the unacked window exceeds the configured limit, the runtime
pauses production and emits a `status` event with
`phase: "backpressure"`, then resumes once acks catch up.

Source: [`../../examples/ack_backpressure/`](../../examples/ack_backpressure/).

```sh
uv run python -m examples.ack_backpressure.server &
uv run python -m examples.ack_backpressure.client
```

## See also

- Guide: [Job events](../guides/job-events.md) — event acknowledgement.
