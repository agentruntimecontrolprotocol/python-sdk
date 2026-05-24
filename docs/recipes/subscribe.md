# Subscribe

A submitter client starts a long-running job; a separate operator
client connects, calls `client.subscribe(job_id, history=True)`, and
replays the prior events before continuing live.

Source: [`../../examples/subscribe/`](../../examples/subscribe/).

```sh
uv run python -m examples.subscribe.server &
uv run python -m examples.subscribe.submitter &
uv run python -m examples.subscribe.observer
```

## See also

- Guide: [Job events](../guides/job-events.md) — Subscribe without a job handle.
