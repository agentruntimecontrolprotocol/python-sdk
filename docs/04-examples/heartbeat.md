---
title: "Heartbeat"
sdk: python
order: 10
kind: example
---

The runtime emits `session.ping` at a short interval; the client
replies with `session.pong`. The example then simulates a stalled
client to surface `HEARTBEAT_LOST` and a `session.error` close.

Source: [`../../examples/heartbeat/`](../../examples/heartbeat/).

```sh
uv run python -m examples.heartbeat.runtime &
uv run python -m examples.heartbeat.client
```

## See also

- Feature: [`../03-features/heartbeats.md`](../03-features/heartbeats.md).
