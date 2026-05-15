---
title: "Stdio transport"
sdk: python
order: 7
kind: example
---

A parent process spawns a child runtime over `StdioTransport` and
submits one job. Demonstrates the child-process subagent topology
in spec §4.2 without any sockets.

Source: [`../../examples/stdio/`](../../examples/stdio/).

```sh
uv run python -m examples.stdio.parent
```

The parent script forks `examples.stdio.child` and connects via
pipes.

## See also

- Reference: [`../05-reference/transport.md`](../05-reference/transport.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §4.2.
