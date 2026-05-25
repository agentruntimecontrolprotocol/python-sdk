# CLI reference

The `arcp` command-line tool is included with the `arcp` package. It provides subcommands for serving agents, submitting jobs, and inspecting event streams.

## Installation

```bash
pip install arcp
# arcp is now on your PATH
```

## Subcommands

### `arcp serve`

Run the built-in demo runtime.

```bash
arcp serve --token demo-token --principal cli-user
```

**Arguments:**

| Argument | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `7777` | Bind port |
| `--token` | required | Demo bearer token to accept |
| `--principal` | `cli-user` | Principal bound to the accepted token |
| `--db` | off | Optional SQLite event log path |

### `arcp submit`

Submit a single job and print the terminal `job.result` JSON.

```bash
arcp submit --url ws://localhost:7777/arcp --token my-bearer-token \
  --agent echo --input '{"url":"https://example.com"}' \
  --lease '{"net.fetch":["https://*"]}'
```

**Arguments:**

| Argument | Default | Description |
|---|---|---|
| `--url` | required | WebSocket URL of the runtime (e.g. `ws://host:7777/arcp`) |
| `--token` | required | Bearer token |
| `--agent` | required | Agent name (optionally `name@version`) |
| `--input` | `null` | JSON-encoded input passed to the agent |
| `--lease` | `{}` | Lease as JSON object (e.g. `{"net.fetch":["https://*"]}`) |

### `arcp tail`

Tail the event stream for a job in real time.

```bash
arcp tail --url ws://localhost:7777/arcp --job-id JOB_ID --token my-bearer-token
```

Prints each `JobEvent` as a JSON line. Press `Ctrl-C` to stop.

### `arcp replay`

Replay a recorded event stream from a SQLite event log.

```bash
arcp replay --db events.sqlite --session SESSION_ID --after-seq 0
```

**Arguments:**

| Argument | Default | Description |
|---|---|---|
| `--db` | required | SQLite event log path |
| `--session` | required | Session id to replay |
| `--after-seq` | `0` | Skip envelopes whose `event_seq` is &lt;= this value |

Each line is one envelope as JSON. Useful for debugging an event stream recorded with `arcp serve --db events.sqlite` after the fact.
