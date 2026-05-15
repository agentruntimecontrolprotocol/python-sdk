---
title: "Subscribe"
sdk: python
order: 13
kind: example
---

A submitter client starts a long-running job; a separate operator
client connects, calls `client.subscribe(job_id, history=True)`, and
replays the prior events before continuing live.

Source: [`../../examples/subscribe/`](../../examples/subscribe/).

```sh
uv run python -m examples.subscribe.runtime &
uv run python -m examples.subscribe.submitter &
uv run python -m examples.subscribe.observer
```

## See also

- Feature: [`../03-features/subscribe.md`](../03-features/subscribe.md).
