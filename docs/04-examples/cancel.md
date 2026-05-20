---
title: "Cancel"
sdk: python
order: 6
kind: example
---

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

- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §7.3.
