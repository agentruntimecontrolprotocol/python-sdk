# List jobs

The client submits three jobs against the same agent, then issues
`session.list_jobs` with status and agent filters plus a small
`limit` to demonstrate cursor paging.

Source: [`../../examples/list_jobs/`](../../examples/list_jobs/).

```sh
uv run python -m examples.list_jobs.server &
uv run python -m examples.list_jobs.client
```

## See also

- Guide: [Jobs](../guides/jobs.md) — List jobs.
