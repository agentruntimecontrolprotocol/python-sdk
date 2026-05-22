# Cancel

The client sends `job.cancel`; the runtime cancels the agent task and
emits a terminal `job.error` with code `CANCELLED`. The agent body
receives `asyncio.CancelledError` and may run cleanup before the
terminal envelope ships.

Source: [`../../examples/cancel/`](../../examples/cancel/).

```sh
uv run python -m examples.cancel.runtime &
uv run python -m examples.cancel.client
```

## See also

- Guide: [Jobs](../guides/jobs.md) — Cancellation.
- Spec: [ARCP v1.1 §7.3](https://arcp.dev/spec/v1.1#section-7.3).
