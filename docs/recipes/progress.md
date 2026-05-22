# Progress

An agent scans a list of files and emits `ctx.progress(done=i,
total=n)` for each item. The client renders the
running tally before consuming the terminal `job.result`.

Source: [`../../examples/progress/`](../../examples/progress/).

```sh
uv run python -m examples.progress.runtime &
uv run python -m examples.progress.client
```

## See also

- Guide: [Job events](../guides/job-events.md) — `job.progress`.
- Guide: [Jobs](../guides/jobs.md) — Job context.
