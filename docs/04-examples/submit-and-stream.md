---
title: "Submit and stream"
sdk: python
order: 1
kind: example
---

The hello-world example: a client submits one job and streams its
events until the terminal `job.result`. Demonstrates the connect /
submit / iterate / close lifecycle without leases, idempotency, or
v1.1 features.

Source: [`../../examples/submit_and_stream/`](../../examples/submit_and_stream/).

Run the two-process WebSocket variant:

```sh
uv run python -m examples.submit_and_stream.runtime &
uv run python -m examples.submit_and_stream.client
```

Or run the single-process paired-transport variant from
[`01-quickstart.md`](../01-quickstart.md).

## See also

- Concepts: [`../02-concepts.md`](../02-concepts.md).
- Reference: [`../05-reference/arcp-client.md`](../05-reference/arcp-client.md).
