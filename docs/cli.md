# CLI reference

The `arcp` command-line tool is included with the `agentruntimecontrolprotocol` package. It provides subcommands for serving agents, submitting jobs, and inspecting event streams.

## Installation

```bash
pip install agentruntimecontrolprotocol
# arcp is now on your PATH
```

## Subcommands

### `arcp serve`

Start an ARCP runtime serving agents from a Python module.

```bash
arcp serve my_module:runtime --host 0.0.0.0 --port 8080
```

**Arguments:**

| Argument | Default | Description |
|---|---|---|
| `MODULE:ATTR` | required | Python import path to an `ARCPRuntime` instance |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8080` | Bind port |
| `--reload` | off | Auto-reload on file changes (dev only) |

### `arcp submit`

Submit a job to a running runtime and print the result.

```bash
arcp submit ws://localhost:8080/arcp summarise '{"url":"https://example.com"}' \
  --token my-bearer-token
```

**Arguments:**

| Argument | Description |
|---|---|
| `URL` | WebSocket URL of the runtime |
| `AGENT` | Agent name |
| `INPUT` | JSON-encoded input (use `@file.json` to read from file) |
| `--token` | Bearer token |
| `--lease-max-cost` | Maximum spend in USD (e.g. `0.10`) |
| `--lease-expires-in` | Maximum wall time in seconds |
| `--idempotency-key` | Idempotency key |
| `--stream` | Print result chunks as they arrive |

### `arcp tail`

Tail the event stream for a job in real time.

```bash
arcp tail ws://localhost:8080/arcp JOB_ID --token my-bearer-token
```

Prints each `JobEvent` as a JSON line. Press `Ctrl-C` to stop.

### `arcp replay`

Replay a recorded event stream from a JSONL file.

```bash
arcp replay events.jsonl
```

Useful for debugging: record a live stream with `arcp tail --output events.jsonl`, then replay it offline.

## Environment variables

All CLI options can also be set via environment variables:

| Variable | CLI equivalent |
|---|---|
| `ARCP_TOKEN` | `--token` |
| `ARCP_HOST` | `arcp serve --host` |
| `ARCP_PORT` | `arcp serve --port` |

## Shell completion

```bash
# bash
arcp --install-completion bash

# zsh
arcp --install-completion zsh

# fish
arcp --install-completion fish
```
