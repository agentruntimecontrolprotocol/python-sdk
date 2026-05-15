---
title: "List jobs"
sdk: python
order: 12
kind: example
---

The client submits three jobs against the same agent, then issues
`session.list_jobs` with status and agent filters plus a small
`limit` to demonstrate cursor paging.

Source: [`../../examples/list_jobs/`](../../examples/list_jobs/).

```sh
uv run python -m examples.list_jobs.runtime &
uv run python -m examples.list_jobs.client
```

## See also

- Feature: [`../03-features/list-jobs.md`](../03-features/list-jobs.md).
