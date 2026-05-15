# heartbeat

Demonstrates spec §6.4: `session.ping` / `session.pong` keepalive on a
5-second cadence declared in `welcome.heartbeat_interval_sec`. The
heartbeat coroutine on the runtime is not a child of the per-connection
TaskGroup — a heartbeat loss therefore signals via a future instead of
raising into sibling tasks.

Advertised features: `("heartbeat",)`.

## Run

```sh
python examples/heartbeat/server.py    # terminal 1
python examples/heartbeat/client.py    # terminal 2
```

Client exits 0 when `welcome.heartbeat_interval_sec == 5` and the long
job runs to a successful terminal (≥ 2 pong round-trips).
