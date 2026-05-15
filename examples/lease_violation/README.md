# lease_violation

Demonstrates spec §13.4 / §9.3: an agent's tool call is rejected by its
lease (`fs.read`-only lease, attempted `fs.write`). The agent emits a
`tool_result` with `body.error.code == "PERMISSION_DENIED"`, logs the
violation, and runs to a successful terminal.

## Run

```sh
python examples/lease_violation/server.py    # terminal 1
python examples/lease_violation/client.py    # terminal 2
```

Client exits 0 when at least one `tool_result` carries
`error.code == "PERMISSION_DENIED"` and the job ends `success`.
