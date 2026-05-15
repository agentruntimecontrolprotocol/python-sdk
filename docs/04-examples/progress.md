---
title: "Progress"
sdk: python
order: 17
kind: example
---

An agent scans a list of files and emits `ctx.progress(current=i,
total=n, units="files")` for each item. The client renders the
running tally before consuming the terminal `job.result`.

Source: [`../../examples/progress/`](../../examples/progress/).

```sh
uv run python -m examples.progress.runtime &
uv run python -m examples.progress.client
```

## See also

- Feature: [`../03-features/progress.md`](../03-features/progress.md).
