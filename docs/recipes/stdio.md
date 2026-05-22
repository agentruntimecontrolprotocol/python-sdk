# Stdio transport

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

- Guide: [Transports](../transports.md) — stdio transport.
- Spec: [ARCP v1.1 §4.2](https://arcp.dev/spec/v1.1#section-4.2).
