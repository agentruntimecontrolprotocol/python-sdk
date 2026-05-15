---
title: "Ack back-pressure"
sdk: python
order: 11
kind: example
---

The runtime emits events faster than the client acknowledges them;
once the unacked window exceeds the configured limit, the runtime
pauses production and emits a `status` event with
`phase: "backpressure"`, then resumes once acks catch up.

Source: [`../../examples/ack_backpressure/`](../../examples/ack_backpressure/).

```sh
uv run python -m examples.ack_backpressure.runtime &
uv run python -m examples.ack_backpressure.client
```

## See also

- Feature: [`../03-features/event-ack.md`](../03-features/event-ack.md).
