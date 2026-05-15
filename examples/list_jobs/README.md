# list_jobs

Demonstrates spec §6.6: `session.list_jobs` with a typed
`ListJobsFilter` and manual cursor pagination. The client walks two
pages of `limit=2` to retrieve three jobs.

Advertised features: `("list_jobs",)`.

## Run

```sh
python examples/list_jobs/server.py    # terminal 1
python examples/list_jobs/client.py    # terminal 2
```

Client exits 0 when the two pages cover three jobs total and
`next_cursor` is `None` only on the last page.
