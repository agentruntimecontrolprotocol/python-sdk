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

Submit a job to a running runtime and print the result.

```bash
arcp submit --url ws://localhost:7777/arcp --agent echo \
  --input '{"url":"https://example.com"}' --token my-bearer-token
```

**Arguments:**

| Argument | Description |
|---|---|
| `--url` | WebSocket URL of the runtime |
| `--agent` | Agent name |
| `--input` | JSON-encoded input |
| `--token` | Bearer token |
| `--lease` | Lease JSON object |

### `arcp tail`

Tail the event stream for a job in real time.

```bash
arcp tail --url ws://localhost:7777/arcp --job-id JOB_ID --token my-bearer-token
```

Prints each `JobEvent` as a JSON line. Press `Ctrl-C` to stop.

### `arcp replay`

Replay a recorded event stream from a JSONL file.

```bash
arcp replay --db events.sqlite --session SESSION_ID
```

Useful for debugging: record a live stream from `tail` and replay it from the SQLite event log.
