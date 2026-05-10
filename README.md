# arcp-py

Reference Python implementation of the Agent Runtime Control Protocol (ARCP) v1.0.

See `RFC-0001-v2.md` for the protocol specification and `PLAN.md` for the
implementation plan.

## Quickstart

```sh
uv sync
uv run pytest
```

Run the minimal example:

```sh
uv run python examples/01_minimal_session.py
```

Run the CLI:

```sh
uv run arcp serve --transport ws --bind localhost:7777
```

## Status

v0.1 — see `CONFORMANCE.md` for implemented vs. deferred RFC sections.
