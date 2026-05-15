---
title: "Heartbeats"
sdk: python
spec_sections: ["§6.4"]
order: 2
kind: feature
---

## What it is

The runtime periodically sends `session.ping` to a peer that
negotiated `heartbeat`; the peer replies with `session.pong` echoing
the ping nonce. If the runtime sees no inbound traffic for a
configured interval, it emits `session.error` with code
`HEARTBEAT_LOST` and closes the transport. v1.0 fallback: no pings
are sent, and idle sessions stay open.

## Feature flag

`heartbeat`

## Wire example

```json
{
  "arcp": "1",
  "id": "01J9SHZ...",
  "type": "session.ping",
  "session_id": "sess_01J9SHX...",
  "payload": {"nonce": "ab12cd34", "sent_at": "2026-05-14T18:21:09Z"}
}
```

```json
{
  "arcp": "1",
  "id": "01J9SHZ...",
  "type": "session.pong",
  "session_id": "sess_01J9SHX...",
  "payload": {"ping_nonce": "ab12cd34", "received_at": "2026-05-14T18:21:09Z"}
}
```

## Python API

```python
from arcp.runtime import ARCPRuntime, RuntimeInfo

runtime = ARCPRuntime(
    runtime=RuntimeInfo(name="demo", version="1.1.0"),
    bearer=verifier,
    heartbeat_interval_sec=15.0,
    heartbeat_timeout_sec=45.0,
)
```

Client side: replies are automatic in `ARCPClient._dispatch`
(`arcp/_client/client.py:L187`). Runtime side: the heartbeat task is
started by `heartbeat_loop` in `arcp/_runtime/session.py:L184` after
the welcome handshake.

## Failure modes

- `HEARTBEAT_LOST` — emitted in `session.error` after the timeout
  (`arcp.errors.HeartbeatLostError`).

## See also

- Example: [`../04-examples/heartbeat.md`](../04-examples/heartbeat.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §6.4.
