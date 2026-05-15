# subscribe

Demonstrates spec §7.6 / §6.6: Client A submits a job; Client B
discovers it via `list_jobs`, subscribes with `history=True` to replay
the tail, observes live events, and then attempts to cancel — which is
denied by the runtime's per-job authorization policy (subscriber is not
the submitter).

Advertised features: `("list_jobs", "subscribe")`.

## Run

```sh
python examples/subscribe/server.py    # terminal 1
python examples/subscribe/client.py    # terminal 2
```

Client exits 0 when B's history replay is non-empty, at least one live
event is tailed, and B's cancel attempt was rejected.
