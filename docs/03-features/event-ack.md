---
title: "Event acknowledgement"
sdk: python
spec_sections: ["§6.5"]
order: 3
kind: feature
---

## What it is

When negotiated, the client sends `session.ack` carrying the highest
event sequence it has processed; the runtime tracks per-session
acked offsets and applies back-pressure when the unacked window
exceeds the configured limit, surfaced to agents as a `status`
event with `phase: "backpressure"`. v1.0 fallback: no acks are sent,
the runtime never pauses.

## Feature flag

`ack`

## Wire example

```json
{
  "arcp": "1.1",
  "id": "01J9SJ0...",
  "type": "session.ack",
  "session_id": "sess_01J9SHX...",
  "payload": {"last_processed_seq": 42}
}
```

## Python API

```python
from arcp.client import ARCPClient, AutoAckOptions

client = ARCPClient(client=..., token=..., auto_ack=AutoAckOptions(every_sec=1.0))
# or manual:
await client.ack(client.latest_event_seq)
```

`auto_ack=True` enables periodic acknowledgement after handshake
(`arcp/_client/client.py:L85`); `auto_ack=AutoAckOptions(...)`
configures cadence. Manual `ARCPClient.ack(seq)` lives at
`arcp/_client/client.py:L435`. Runtime processing is in
`ARCPRuntime._handle_ack` at `arcp/_runtime/server.py:L411`.

## Failure modes

No error code is emitted for back-pressure itself; the runtime
publishes a `status` event whose `phase` indicates the pause and
resume transitions. `INVALID_REQUEST` is raised by the runtime on
malformed `last_processed_seq` (negative or non-integer).

## See also

- Example: [`../04-examples/ack-backpressure.md`](../04-examples/ack-backpressure.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §6.5.
