# ack_backpressure

Demonstrates spec §6.5 / §8.2: the client opts into auto-ack but
deliberately starves the ack pump (`every_n=10_000`). The server agent
watches `session.latest_event_seq - state.last_acked_seq` and emits
`status { phase: "back_pressure" }` when the gap exceeds the threshold.

Advertised features: `("ack",)`.

## Run

```sh
python examples/ack_backpressure/server.py    # terminal 1
python examples/ack_backpressure/client.py    # terminal 2
```

Client exits 0 when ≥ 1 `back_pressure` status envelope is observed.
