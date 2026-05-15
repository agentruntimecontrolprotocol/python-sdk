# stdio

Demonstrates spec §4.2 / §22: ARCP over the parent's stdin/stdout pipes.
The client spawns `server.py` as a subprocess and talks NDJSON across
the pipes. `runner.py` is a single-command entrypoint matching TS's
`stdio/` exception to the two-terminal rule.

## Run

Two-process form:

```sh
python examples/stdio/client.py
```

(The client spawns `server.py` itself — no separate terminal needed.)

Single-command form:

```sh
python examples/stdio/runner.py
```

Client exits 0 after the child exits and the result reaches
`final_status == "success"`.
