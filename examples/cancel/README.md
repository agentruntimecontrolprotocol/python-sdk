# cancel

Demonstrates spec §7.4: client sends `job.cancel { reason }`; the runtime
cancels the agent's task; the in-flight `await` raises `CancelledError`;
the runtime emits `job.error { final_status: "cancelled" }`.

## Run

```sh
python examples/cancel/server.py    # terminal 1
python examples/cancel/client.py    # terminal 2
```

Client exits 0 when the terminal arrives within 30 s of the cancel.
