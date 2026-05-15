---
title: "Host: ASGI"
sdk: python
order: 20
kind: example
---

Mounts `arcp.middleware.asgi.arcp_asgi_app(runtime,
allowed_hosts=[...])` at `/arcp` inside a Starlette application,
serving ARCP alongside ordinary HTTP routes via uvicorn.

Source: [`../../examples/host_asgi/`](../../examples/host_asgi/).

```sh
uv run python -m examples.host_asgi.server &
uv run python -m examples.host_asgi.client
```

## See also

- Reference: [`../05-reference/middleware-asgi.md`](../05-reference/middleware-asgi.md).
